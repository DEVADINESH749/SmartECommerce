from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import Order, OrderItem, Payment, Product, User


ORDER_STATUSES = (
    'PENDING',
    'CONFIRMED',
    'PROCESSING',
    'SHIPPED',
    'DELIVERED',
    'CANCELLED',
)
PAYMENT_STATUSES = ('PENDING', 'SUCCEEDED', 'FAILED', 'CANCELLED')
REVENUE_ORDER_STATUSES = ('CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED')
DATE_FILTERS = (
    ('today', 'Today'),
    ('last_7_days', 'Last 7 days'),
    ('last_30_days', 'Last 30 days'),
    ('this_month', 'This month'),
    ('this_year', 'This year'),
    ('custom', 'Custom range'),
)
LOW_STOCK_THRESHOLD = 5


def resolve_date_range(params, today=None):
    today = today or timezone.localdate()
    period = params.get('period', 'this_month')
    error = ''

    if period == 'today':
        start_date = end_date = today
    elif period == 'last_7_days':
        start_date, end_date = today - timedelta(days=6), today
    elif period == 'last_30_days':
        start_date, end_date = today - timedelta(days=29), today
    elif period == 'this_year':
        start_date, end_date = date(today.year, 1, 1), today
    elif period == 'custom':
        start_date = parse_date(params.get('start_date', ''))
        end_date = parse_date(params.get('end_date', ''))
        if not start_date or not end_date or end_date < start_date:
            error = 'Choose a valid start and end date.'
            period = 'this_month'
            start_date, end_date = date(today.year, today.month, 1), today
        elif (end_date - start_date).days > 365:
            error = 'Custom ranges are limited to 366 days.'
            period = 'this_month'
            start_date, end_date = date(today.year, today.month, 1), today
    else:
        if period != 'this_month':
            error = 'Unknown date filter; showing this month.'
        period = 'this_month'
        start_date, end_date = date(today.year, today.month, 1), today

    start_at = datetime.combine(start_date, time.min)
    end_before = datetime.combine(end_date + timedelta(days=1), time.min)
    if settings.USE_TZ:
        start_at = timezone.make_aware(start_at, timezone.get_current_timezone())
        end_before = timezone.make_aware(end_before, timezone.get_current_timezone())

    return {
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'start_at': start_at,
        'end_before': end_before,
        'error': error,
    }


def _zero_filled_daily_sales(start_date, end_date, rows):
    sales_by_date = {row['bucket']: row for row in rows}
    sales = []
    for offset in range((end_date - start_date).days + 1):
        day = start_date + timedelta(days=offset)
        row = sales_by_date.get(day, {})
        sales.append({
            'date': day,
            'label': day.strftime('%b %d').replace(' 0', ' '),
            'order_count': row.get('order_count', 0),
            'revenue': row.get('revenue') or Decimal('0.00'),
        })
    return sales


def _zero_filled_monthly_sales(start_date, end_date, rows):
    sales_by_month = {
        (row['bucket'].year, row['bucket'].month): row
        for row in rows
    }
    current = date(start_date.year, start_date.month, 1)
    final = date(end_date.year, end_date.month, 1)
    sales = []
    while current <= final:
        row = sales_by_month.get((current.year, current.month), {})
        sales.append({
            'month': current,
            'label': current.strftime('%b %Y'),
            'order_count': row.get('order_count', 0),
            'revenue': row.get('revenue') or Decimal('0.00'),
        })
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return sales


def _with_bar_heights(rows):
    maximum = max((row['revenue'] for row in rows), default=Decimal('0.00'))
    return [
        {
            **row,
            'bar_height': (
                max(6, int(row['revenue'] * 100 / maximum))
                if maximum and row['revenue']
                else 0
            ),
        }
        for row in rows
    ]


def get_analytics(params):
    selected = resolve_date_range(params)
    order_window = Order.objects.filter(
        created_at__gte=selected['start_at'],
        created_at__lt=selected['end_before'],
    )
    revenue_orders = order_window.filter(status__in=REVENUE_ORDER_STATUSES)
    order_status_rows = {
        row['status']: row['count']
        for row in order_window.values('status').annotate(count=Count('id'))
    }

    payment_window = Payment.objects.filter(
        created_at__gte=selected['start_at'],
        created_at__lt=selected['end_before'],
    )
    payment_status_rows = {
        row['status']: row['count']
        for row in payment_window.values('status').annotate(count=Count('id'))
    }
    successful_payment_revenue = payment_window.filter(status='SUCCEEDED').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')

    daily_rows = list(
        revenue_orders.annotate(bucket=TruncDate('created_at'))
        .values('bucket')
        .annotate(order_count=Count('id'), revenue=Sum('total_amount'))
        .order_by('bucket')
    )
    monthly_rows = list(
        revenue_orders.annotate(bucket=TruncMonth('created_at'))
        .values('bucket')
        .annotate(order_count=Count('id'), revenue=Sum('total_amount'))
        .order_by('bucket')
    )
    daily_sales = _with_bar_heights(
        _zero_filled_daily_sales(selected['start_date'], selected['end_date'], daily_rows)
    )
    monthly_sales = _with_bar_heights(
        _zero_filled_monthly_sales(selected['start_date'], selected['end_date'], monthly_rows)
    )

    top_products = list(
        OrderItem.objects.filter(
            order__created_at__gte=selected['start_at'],
            order__created_at__lt=selected['end_before'],
            order__status__in=REVENUE_ORDER_STATUSES,
        )
        .values('product_id', 'product_name')
        .annotate(quantity_sold=Sum('quantity'), revenue=Sum('subtotal'))
        .order_by('-quantity_sold', 'product_name')[:10]
    )
    low_stock = list(
        Product.objects.filter(is_active=True, stock__lte=LOW_STOCK_THRESHOLD)
        .order_by('stock', 'name')
        .values('id', 'name', 'stock', 'price')
    )
    order_status = [
        {'status': status, 'count': order_status_rows.get(status, 0)}
        for status in ORDER_STATUSES
    ]
    payment_status = [
        {'status': status, 'count': payment_status_rows.get(status, 0)}
        for status in PAYMENT_STATUSES
    ]
    revenue_total = revenue_orders.aggregate(total=Sum('total_amount'))['total']

    return {
        'period': selected['period'],
        'start_date': selected['start_date'],
        'end_date': selected['end_date'],
        'date_error': selected['error'],
        'date_filters': DATE_FILTERS,
        'start_date_input': params.get('start_date', selected['start_date'].isoformat()),
        'end_date_input': params.get('end_date', selected['end_date'].isoformat()),
        'summary': {
            'total_orders': order_window.count(),
            'confirmed_orders': revenue_orders.count(),
            'total_revenue': revenue_total or Decimal('0.00'),
            'total_products': Product.objects.count(),
            'low_stock_products': len(low_stock),
            'total_customers': User.objects.filter(role='customer').count(),
            'successful_payment_revenue': successful_payment_revenue,
        },
        'daily_sales': daily_sales,
        'monthly_sales': monthly_sales,
        'top_products': top_products,
        'low_stock': low_stock,
        'order_status': order_status,
        'payment_status': payment_status,
    }

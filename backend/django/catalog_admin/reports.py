from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate

from .analytics import (
    DATE_FILTERS,
    LOW_STOCK_THRESHOLD,
    ORDER_STATUSES,
    PAYMENT_STATUSES,
    REVENUE_ORDER_STATUSES,
    resolve_date_range,
)
from .models import Order, OrderItem, Payment, Product


ZERO = Decimal('0.00')


def build_reports(params):
    selected = resolve_date_range(params)
    date_filter = {
        'created_at__gte': selected['start_at'],
        'created_at__lt': selected['end_before'],
    }
    orders = Order.objects.filter(**date_filter).select_related('user').order_by('-created_at', '-id')
    successful_orders = Order.objects.filter(
        **date_filter,
        status__in=REVENUE_ORDER_STATUSES,
    )
    sales_totals = successful_orders.aggregate(
        order_count=Count('id'),
        revenue=Sum('total_amount'),
        average_order_value=Avg('total_amount'),
    )
    sales_order_rows = {
        row['day']: row
        for row in successful_orders.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(order_count=Count('id'), revenue=Sum('total_amount'))
        .order_by('day')
    }
    sales_quantity_rows = {
        row['day']: row['quantity_sold'] or 0
        for row in OrderItem.objects.filter(
            order__created_at__gte=selected['start_at'],
            order__created_at__lt=selected['end_before'],
            order__status__in=REVENUE_ORDER_STATUSES,
        )
        .annotate(day=TruncDate('order__created_at'))
        .values('day')
        .annotate(quantity_sold=Sum('quantity'))
        .order_by('day')
    }
    sales = []
    for offset in range((selected['end_date'] - selected['start_date']).days + 1):
        day = selected['start_date'] + timedelta(days=offset)
        order_row = sales_order_rows.get(day, {})
        sales.append({
            'date': day,
            'orders': order_row.get('order_count', 0),
            'quantity_sold': sales_quantity_rows.get(day, 0),
            'revenue': order_row.get('revenue') or ZERO,
        })

    order_status_rows = {
        row['status']: row['count']
        for row in orders.values('status').annotate(count=Count('id'))
    }
    order_status = [
        {'status': status, 'count': order_status_rows.get(status, 0)}
        for status in ORDER_STATUSES
    ]

    products = Product.objects.order_by('id')
    product_summary = products.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_active=True)),
        inactive=Count('id', filter=Q(is_active=False)),
    )
    low_stock = Product.objects.filter(
        is_active=True,
        stock__lte=LOW_STOCK_THRESHOLD,
    ).order_by('stock', 'name')
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

    payments = Payment.objects.filter(**date_filter).select_related('order', 'user').order_by('-created_at', '-id')
    payment_status_rows = {
        row['status']: row['count']
        for row in payments.values('status').annotate(count=Count('id'))
    }
    payment_status = [
        {'status': status, 'count': payment_status_rows.get(status, 0)}
        for status in PAYMENT_STATUSES
    ]
    successful_payments = payments.filter(status='SUCCEEDED')
    payment_summary = successful_payments.aggregate(
        count=Count('id'),
        revenue=Sum('amount'),
    )

    return {
        'period': selected['period'],
        'start_date': selected['start_date'],
        'end_date': selected['end_date'],
        'date_error': selected['error'],
        'date_filters': DATE_FILTERS,
        'start_date_input': params.get('start_date', selected['start_date'].isoformat()),
        'end_date_input': params.get('end_date', selected['end_date'].isoformat()),
        'sales': sales,
        'sales_summary': {
            'successful_orders': sales_totals['order_count'] or 0,
            'revenue': sales_totals['revenue'] or ZERO,
            'quantity_sold': sum(sales_quantity_rows.values()),
            'average_order_value': sales_totals['average_order_value'] or ZERO,
        },
        'orders': orders,
        'order_status': order_status,
        'products': products,
        'product_summary': {
            'total': product_summary['total'] or 0,
            'active': product_summary['active'] or 0,
            'inactive': product_summary['inactive'] or 0,
            'low_stock': low_stock.count(),
        },
        'low_stock': low_stock,
        'top_products': top_products,
        'payments': payments,
        'payment_status': payment_status,
        'payment_summary': {
            'successful_count': payment_summary['count'] or 0,
            'successful_revenue': payment_summary['revenue'] or ZERO,
        },
    }

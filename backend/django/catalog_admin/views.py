import csv
import io
from html import escape
from pathlib import Path

from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .analytics import get_analytics
from .reports import build_reports


CSV_COLUMNS = {
    'sales': ('Date', 'Orders', 'Quantity Sold', 'Revenue'),
    'orders': ('Order ID', 'User', 'Total Amount', 'Status', 'Created Date', 'Updated Date'),
    'inventory': ('Product ID', 'Product Name', 'Category', 'Price', 'Current Stock', 'Popularity', 'Active'),
    'payments': ('Payment ID', 'Order ID', 'User', 'Amount', 'Currency', 'Status', 'Created Date'),
}


def analytics_dashboard(request):
    context = get_analytics(request.GET)
    return render(request, 'catalog_admin/analytics.html', context)


def _report_context(request):
    data = build_reports(request.GET)
    data['export_query'] = request.GET.urlencode()
    data['orders_page'] = Paginator(data['orders'], 25).get_page(request.GET.get('orders_page'))
    data['products_page'] = Paginator(data['products'], 25).get_page(request.GET.get('products_page'))
    data['payments_page'] = Paginator(data['payments'], 25).get_page(request.GET.get('payments_page'))
    return data


@require_GET
def reports_dashboard(request):
    return render(request, 'catalog_admin/reports.html', _report_context(request))


def _csv_safe(value):
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r')):
        return "'" + value
    return value


def _csv_response(report_type, rows):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(CSV_COLUMNS[report_type])
    for row in rows:
        writer.writerow([_csv_safe(value) for value in row])
    return response


def _sales_csv_rows(data):
    for row in data['sales']:
        yield (
            row['date'].isoformat(),
            row['orders'],
            row['quantity_sold'],
            f"{row['revenue']:.2f}",
        )
    summary = data['sales_summary']
    yield (
        'Total',
        summary['successful_orders'],
        summary['quantity_sold'],
        f"{summary['revenue']:.2f}",
    )


def _orders_csv_rows(data):
    for order in data['orders'].iterator(chunk_size=1000):
        yield (
            order.id,
            f'{order.user.name} (#{order.user_id})',
            f'{order.total_amount:.2f}',
            order.status,
            timezone.localtime(order.created_at).isoformat(),
            timezone.localtime(order.updated_at).isoformat(),
        )


def _inventory_csv_rows(data):
    for product in data['products'].iterator(chunk_size=1000):
        yield (
            product.id,
            product.name,
            product.category,
            f'{product.price:.2f}',
            product.stock,
            product.popularity,
            'Yes' if product.is_active else 'No',
        )


def _payments_csv_rows(data):
    for payment in data['payments'].iterator(chunk_size=1000):
        yield (
            payment.id,
            payment.order_id,
            f'{payment.user.name} (#{payment.user_id})',
            f'{payment.amount:.2f}',
            payment.currency.upper(),
            payment.status,
            timezone.localtime(payment.created_at).isoformat(),
        )


def _register_report_font():
    font_name = 'ReportSans'
    if font_name in pdfmetrics.getRegisteredFontNames():
        return font_name, True

    candidates = (
        Path('C:/Windows/Fonts/arial.ttf'),
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
        Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'),
        Path(__import__('reportlab').__file__).parent / 'fonts' / 'Vera.ttf',
    )
    for path in candidates:
        if not path.exists():
            continue
        try:
            font = TTFont(font_name, str(path))
            supports_rupee = 0x20B9 in font.face.charWidths
            if supports_rupee:
                pdfmetrics.registerFont(font)
                return font_name, True
        except (OSError, KeyError, ValueError):
            continue
    return 'Helvetica', False


def _pdf_text(value, rupee_supported):
    text = str(value)
    if not rupee_supported:
        text = text.replace('₹', 'INR ')
    return escape(text).replace('\n', '<br/>')


def _make_pdf(report_type, data):
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(letter),
        rightMargin=0.45 * inch,
        leftMargin=0.45 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
        title=f'{report_type.title()} Report',
        author='Smart E-Commerce',
    )
    font_name, rupee_supported = _register_report_font()
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        'ReportBody', parent=styles['BodyText'], fontName=font_name,
        fontSize=8, leading=10, alignment=TA_LEFT,
    )
    title_style = ParagraphStyle(
        'ReportTitle', parent=styles['Title'], fontName=font_name,
        fontSize=18, leading=22, alignment=TA_LEFT,
        textColor=colors.HexColor('#173b3a'),
    )
    generated_at = timezone.localtime().strftime('%b %d, %Y %H:%M %Z')
    date_range = f"{data['start_date']:%b %d, %Y} - {data['end_date']:%b %d, %Y}"
    content = [
        Paragraph('SMART E-COMMERCE', title_style),
        Paragraph(f'{report_type.title()} Report', styles['Heading2']),
        Paragraph(f'Generated: {escape(generated_at)}', body_style),
        Paragraph(f'Date Range: {escape(date_range)}', body_style),
        Spacer(1, 12),
    ]

    if report_type == 'sales':
        summary = data['sales_summary']
        content.extend([
            Paragraph(f"Successful Orders: {summary['successful_orders']}", body_style),
            Paragraph(f"Total Revenue: {_pdf_text(f'₹{summary['revenue']:.2f}', rupee_supported)}", body_style),
            Paragraph(f"Quantity Sold: {summary['quantity_sold']}", body_style),
            Paragraph(f"Average Order Value: {_pdf_text(f'₹{summary['average_order_value']:.2f}', rupee_supported)}", body_style),
            Spacer(1, 12),
        ])
        rows = [['Date', 'Orders', 'Quantity Sold', 'Revenue']]
        rows.extend([
            [row['date'].strftime('%b %d, %Y'), row['orders'], row['quantity_sold'], f"₹{row['revenue']:.2f}"]
            for row in data['sales']
        ])
        rows.append(['Total', summary['successful_orders'], summary['quantity_sold'], f"₹{summary['revenue']:.2f}"])
    else:
        rows = [['Order ID', 'User', 'Total Amount', 'Status', 'Created', 'Updated']]
        for order in data['orders'].iterator(chunk_size=1000):
            rows.append([
                order.id,
                f'{order.user.name} (#{order.user_id})',
                f'₹{order.total_amount:.2f}',
                order.status,
                timezone.localtime(order.created_at).strftime('%Y-%m-%d %H:%M'),
                timezone.localtime(order.updated_at).strftime('%Y-%m-%d %H:%M'),
            ])
        content.append(Paragraph('Order Status Summary', styles['Heading3']))
        status_summary = ' · '.join(f"{row['status']}: {row['count']}" for row in data['order_status'])
        content.append(Paragraph(escape(status_summary), body_style))
        content.append(Spacer(1, 10))

    safe_rows = [
        [Paragraph(_pdf_text(cell, rupee_supported), body_style) for cell in row]
        for row in rows
    ]
    table = Table(safe_rows, repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e6efeb')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#173b3a')),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#cbd8d3')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f8f6')]),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    content.append(table)
    document.build(content)
    return output.getvalue()


@require_GET
def reports_export(request, report_file):
    if '.' not in report_file:
        return HttpResponse(status=404)
    report_type, extension = report_file.rsplit('.', 1)
    if report_type not in CSV_COLUMNS or extension not in {'csv', 'pdf'}:
        return HttpResponse(status=404)
    if extension == 'pdf' and report_type not in {'sales', 'orders'}:
        return HttpResponse(status=404)

    data = build_reports(request.GET)
    if extension == 'csv':
        row_builders = {
            'sales': _sales_csv_rows,
            'orders': _orders_csv_rows,
            'inventory': _inventory_csv_rows,
            'payments': _payments_csv_rows,
        }
        return _csv_response(report_type, row_builders[report_type](data))

    response = HttpResponse(_make_pdf(report_type, data), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report.pdf"'
    return response

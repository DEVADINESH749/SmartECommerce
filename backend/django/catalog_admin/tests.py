from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import RequestFactory, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .admin import OrderAdmin
from .models import Notification, Order, OrderItem, Payment, Product, User


class AdminIntegrationTests(TransactionTestCase):
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.integration_models = (User, Product, Order, OrderItem, Payment, Notification)
        with connections['default'].schema_editor() as schema_editor:
            for model in cls.integration_models:
                schema_editor.create_model(model)

    @classmethod
    def tearDownClass(cls):
        with connections['default'].schema_editor() as schema_editor:
            for model in reversed(cls.integration_models):
                schema_editor.delete_model(model)
        super().tearDownClass()

    def setUp(self):
        self.additional_orders = []
        self.additional_products = []
        self.api_user = User.objects.create(
            name='Admin Test Customer',
            email='admin-customer@example.invalid',
            password_hash='never-render-this-hash',
            role='customer',
            is_active=True,
        )
        self.product = Product.objects.create(
            name='Wireless Mouse',
            description='Test fixture product',
            category='Accessories',
            price=Decimal('25.00'),
            stock=8,
            popularity=4,
            image=None,
            is_active=True,
            created_at=timezone.now(),
        )
        now = timezone.now()
        self.order = Order.objects.create(
            user=self.api_user,
            total_amount=Decimal('50.00'),
            status='SHIPPED',
            stock_restored=False,
            created_at=now - timedelta(days=1),
            updated_at=now,
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal('25.00'),
            quantity=2,
            subtotal=Decimal('50.00'),
        )
        self.payment = Payment.objects.create(
            order=self.order,
            user=self.api_user,
            amount=Decimal('50.00'),
            currency='usd',
            status='FAILED',
            stripe_payment_intent_id='pi_test_admin_view',
            created_at=now,
            updated_at=now,
        )
        Notification.objects.create(
            user=self.api_user,
            title='Order shipped',
            message='Your order has shipped.',
            notification_type='ORDER_SHIPPED',
            is_read=False,
            created_at=now,
            event_key='admin-test-order-shipped',
        )
        self.admin_user = get_user_model().objects.create_user(
            username='module9-admin',
            email='module9-admin@example.invalid',
            password=None,
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.admin_user)

    def tearDown(self):
        all_orders = [self.order, *self.additional_orders]
        Payment.objects.filter(order__in=all_orders).delete()
        Notification.objects.filter(user=self.api_user).delete()
        OrderItem.objects.filter(order__in=all_orders).delete()
        for order in reversed(self.additional_orders):
            order.delete()
        self.order.delete()
        for product in reversed(self.additional_products):
            product.delete()
        self.product.delete()
        self.api_user.delete()
        super().tearDown()

    def test_admin_login_and_all_sections_load(self):
        self.assertEqual(self.client.get('/admin/').status_code, 200)
        sections = {
            'user': 'admin-customer@example.invalid',
            'product': 'Wireless Mouse',
            'order': 'admin-customer@example.invalid',
            'orderitem': 'Wireless Mouse',
            'payment': 'pi_test_admin_view',
            'notification': 'Your order has shipped.',
        }
        for section, expected_content in sections.items():
            with self.subTest(section=section):
                response = self.client.get(
                    reverse(f'admin:catalog_admin_{section}_changelist')
                )
                self.assertContains(response, expected_content)

    def test_non_staff_user_cannot_access_admin(self):
        self.client.logout()
        customer = get_user_model().objects.create_user(
            username='module9-customer',
            password=None,
        )
        self.client.force_login(customer)
        self.assertIn(self.client.get('/admin/').status_code, (302, 403))

    def test_product_search_and_untracked_updated_at_display(self):
        response = self.client.get(
            reverse('admin:catalog_admin_product_changelist'),
            {'q': 'Wireless Mouse'},
        )
        self.assertContains(response, 'Wireless Mouse')
        self.assertContains(response, 'Not tracked by this table')

    def test_order_payment_and_notification_filters(self):
        order_response = self.client.get(
            reverse('admin:catalog_admin_order_changelist'),
            {'status__exact': 'SHIPPED'},
        )
        payment_response = self.client.get(
            reverse('admin:catalog_admin_payment_changelist'),
            {'status__exact': 'FAILED'},
        )
        notification_response = self.client.get(
            reverse('admin:catalog_admin_notification_changelist'),
            {'is_read__exact': '0'},
        )
        self.assertEqual(list(order_response.context['cl'].result_list), [self.order])
        self.assertContains(payment_response, 'pi_test_admin_view')
        self.assertContains(notification_response, 'Your order has shipped.')

    def test_sensitive_user_and_payment_fields_are_not_exposed(self):
        user_response = self.client.get(
            reverse('admin:catalog_admin_user_change', args=(self.api_user.pk,))
        )
        payment_response = self.client.get(
            reverse('admin:catalog_admin_payment_change', args=(self.payment.pk,))
        )
        self.assertNotContains(user_response, 'password_hash')
        self.assertNotContains(user_response, 'never-render-this-hash')
        self.assertNotContains(payment_response, 'secret_key')
        self.assertNotContains(payment_response, 'client_secret')

    def test_order_status_admin_reuses_shared_transition_service(self):
        request = RequestFactory().post('/admin/')
        request.user = self.admin_user
        self.order.status = 'PROCESSING'
        order_admin = OrderAdmin(Order, None)
        with patch('catalog_admin.admin.update_order_status') as update_status:
            order_admin.save_model(request, self.order, form=None, change=True)
        update_status.assert_called_once_with(self.order.pk, 'PROCESSING')

    def test_analytics_dashboard_requires_staff(self):
        response = self.client.get('/admin/analytics/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Commerce analytics')

        self.client.logout()
        staff_user = get_user_model().objects.create_user(
            username='analytics-staff',
            password=None,
            is_staff=True,
        )
        self.client.force_login(staff_user)
        self.assertEqual(self.client.get('/admin/analytics/').status_code, 200)

        self.client.logout()
        customer = get_user_model().objects.create_user(
            username='analytics-customer',
            password=None,
        )
        self.client.force_login(customer)
        response = self.client.get('/admin/analytics/')
        self.assertIn(response.status_code, (302, 403))

    def test_analytics_aggregates_exclude_cancelled_and_filter_dates(self):
        now = timezone.now()
        cancelled_order = Order.objects.create(
            user=self.api_user,
            total_amount=Decimal('75.00'),
            status='CANCELLED',
            stock_restored=True,
            created_at=now,
            updated_at=now,
        )
        old_order = Order.objects.create(
            user=self.api_user,
            total_amount=Decimal('90.00'),
            status='CONFIRMED',
            stock_restored=False,
            created_at=now - timedelta(days=40),
            updated_at=now - timedelta(days=40),
        )
        self.additional_orders.extend((cancelled_order, old_order))
        OrderItem.objects.create(
            order=cancelled_order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal('25.00'),
            quantity=3,
            subtotal=Decimal('75.00'),
        )
        OrderItem.objects.create(
            order=old_order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal('25.00'),
            quantity=4,
            subtotal=Decimal('100.00'),
        )
        Payment.objects.create(
            order=self.order,
            user=self.api_user,
            amount=Decimal('50.00'),
            currency='inr',
            status='SUCCEEDED',
            stripe_payment_intent_id='pi_test_analytics_success',
            created_at=now,
            updated_at=now,
        )
        low_stock_product = Product.objects.create(
            name='Analytics Low Stock',
            description=None,
            category='Test',
            price=Decimal('12.00'),
            stock=5,
            popularity=0,
            image=None,
            is_active=True,
            created_at=now,
        )
        inactive_product = Product.objects.create(
            name='Analytics Inactive',
            description=None,
            category='Test',
            price=Decimal('15.00'),
            stock=0,
            popularity=0,
            image=None,
            is_active=False,
            created_at=now,
        )
        self.additional_products.extend((low_stock_product, inactive_product))

        today = timezone.localdate()
        response = self.client.get('/admin/analytics/', {
            'period': 'custom',
            'start_date': (today - timedelta(days=6)).isoformat(),
            'end_date': today.isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        summary = response.context['summary']
        self.assertEqual(summary['total_orders'], 2)
        self.assertEqual(summary['confirmed_orders'], 1)
        self.assertEqual(summary['total_revenue'], Decimal('50.00'))
        self.assertEqual(summary['total_products'], 3)
        self.assertEqual(summary['low_stock_products'], 1)
        self.assertEqual(summary['total_customers'], 1)
        self.assertEqual(summary['successful_payment_revenue'], Decimal('50.00'))
        self.assertEqual(response.context['top_products'][0]['quantity_sold'], 2)
        self.assertEqual(response.context['top_products'][0]['revenue'], Decimal('50.00'))
        self.assertEqual(response.context['low_stock'][0]['id'], low_stock_product.id)
        self.assertEqual(
            {row['status']: row['count'] for row in response.context['order_status']},
            {'PENDING': 0, 'CONFIRMED': 0, 'PROCESSING': 0, 'SHIPPED': 1, 'DELIVERED': 0, 'CANCELLED': 1},
        )
        self.assertEqual(
            {row['status']: row['count'] for row in response.context['payment_status']},
            {'PENDING': 0, 'SUCCEEDED': 1, 'FAILED': 1, 'CANCELLED': 0},
        )
        self.assertEqual(sum(day['order_count'] for day in response.context['daily_sales']), 1)

        today_response = self.client.get('/admin/analytics/', {'period': 'today'})
        self.assertEqual(today_response.status_code, 200)
        self.assertEqual(today_response.context['summary']['total_orders'], 1)

    def _create_report_order(self, status, amount, quantity, created_at):
        order = Order.objects.create(
            user=self.api_user,
            total_amount=Decimal(amount),
            status=status,
            stock_restored=status == 'CANCELLED',
            created_at=created_at,
            updated_at=created_at,
        )
        self.additional_orders.append(order)
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal('25.00'),
            quantity=quantity,
            subtotal=Decimal(amount),
        )
        return order

    def test_reports_sales_orders_inventory_payments_and_date_filtering(self):
        now = timezone.now()
        confirmed = self._create_report_order('CONFIRMED', '40.00', 1, now)
        pending = self._create_report_order('PENDING', '30.00', 5, now)
        cancelled = self._create_report_order('CANCELLED', '100.00', 9, now)
        active_low_stock = Product.objects.create(
            name='Report Low Stock',
            description=None,
            category='Test',
            price=Decimal('12.00'),
            stock=5,
            popularity=2,
            image=None,
            is_active=True,
            created_at=now,
        )
        inactive_low_stock = Product.objects.create(
            name='Report Inactive Stock',
            description=None,
            category='Test',
            price=Decimal('15.00'),
            stock=0,
            popularity=1,
            image=None,
            is_active=False,
            created_at=now,
        )
        self.additional_products.extend((active_low_stock, inactive_low_stock))
        for order, status, amount, suffix in (
            (confirmed, 'SUCCEEDED', '40.00', 'confirmed'),
            (pending, 'PENDING', '30.00', 'pending'),
            (cancelled, 'CANCELLED', '100.00', 'cancelled'),
        ):
            Payment.objects.create(
                order=order,
                user=self.api_user,
                amount=Decimal(amount),
                currency='inr',
                status=status,
                stripe_payment_intent_id=f'pi_report_{suffix}',
                created_at=now,
                updated_at=now,
            )

        today = timezone.localdate()
        response = self.client.get('/admin/reports/', {'period': 'last_7_days'})
        self.assertEqual(response.status_code, 200)
        sales = response.context['sales_summary']
        self.assertEqual(sales['successful_orders'], 2)
        self.assertEqual(sales['revenue'], Decimal('90.00'))
        self.assertEqual(sales['quantity_sold'], 3)
        self.assertEqual(sales['average_order_value'], Decimal('45.00'))
        self.assertEqual(response.context['top_products'][0]['quantity_sold'], 3)
        self.assertEqual(response.context['top_products'][0]['revenue'], Decimal('90.00'))
        self.assertEqual(response.context['product_summary']['total'], 3)
        self.assertEqual(response.context['product_summary']['active'], 2)
        self.assertEqual(response.context['product_summary']['inactive'], 1)
        self.assertEqual(response.context['product_summary']['low_stock'], 1)
        self.assertEqual(response.context['low_stock'].get().id, active_low_stock.id)
        self.assertEqual(
            {row['status']: row['count'] for row in response.context['order_status']},
            {'PENDING': 1, 'CONFIRMED': 1, 'PROCESSING': 0, 'SHIPPED': 1, 'DELIVERED': 0, 'CANCELLED': 1},
        )
        self.assertEqual(
            {row['status']: row['count'] for row in response.context['payment_status']},
            {'PENDING': 1, 'SUCCEEDED': 1, 'FAILED': 1, 'CANCELLED': 1},
        )
        self.assertEqual(response.context['payment_summary']['successful_count'], 1)
        self.assertEqual(response.context['payment_summary']['successful_revenue'], Decimal('40.00'))
        self.assertContains(response, 'Report Low Stock')
        self.assertContains(response, 'Report Inactive Stock')
        self.assertNotIn(
            inactive_low_stock.id,
            response.context['low_stock'].values_list('id', flat=True),
        )

        today_response = self.client.get('/admin/reports/', {
            'period': 'custom',
            'start_date': today.isoformat(),
            'end_date': today.isoformat(),
        })
        self.assertEqual(today_response.status_code, 200)
        self.assertEqual(today_response.context['sales_summary']['revenue'], Decimal('40.00'))
        self.assertEqual(today_response.context['sales_summary']['quantity_sold'], 1)
        self.assertEqual(today_response.context['orders_page'].paginator.count, 3)

    def test_report_csv_exports_have_headers_and_filtered_rows(self):
        expected_headers = {
            'sales.csv': 'Date,Orders,Quantity Sold,Revenue',
            'orders.csv': 'Order ID,User,Total Amount,Status,Created Date,Updated Date',
            'inventory.csv': 'Product ID,Product Name,Category,Price,Current Stock,Popularity,Active',
            'payments.csv': 'Payment ID,Order ID,User,Amount,Currency,Status,Created Date',
        }
        for report_file, header in expected_headers.items():
            with self.subTest(report_file=report_file):
                response = self.client.get(
                    reverse('admin_reports_export', args=(report_file,)),
                    {'period': 'last_7_days'},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
                content = response.content.decode('utf-8-sig')
                self.assertTrue(content.startswith(header))
        sales_response = self.client.get(
            reverse('admin_reports_export', args=('sales.csv',)),
            {'period': 'this_month'},
        )
        self.assertIn('Total,1,2,50.00', sales_response.content.decode('utf-8-sig'))

    def test_report_pdf_exports_return_pdf_documents(self):
        for report_file, report_title in (
            ('sales.pdf', 'Sales Report'),
            ('orders.pdf', 'Orders Report'),
        ):
            with self.subTest(report_file=report_file):
                response = self.client.get(
                    reverse('admin_reports_export', args=(report_file,)),
                    {'period': 'this_month'},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Content-Type'], 'application/pdf')
                self.assertTrue(response.content.startswith(b'%PDF-'))
                self.assertIn(report_file.replace('.pdf', '_report.pdf'), response['Content-Disposition'])

    def test_reports_require_staff_for_page_and_exports(self):
        self.client.logout()
        response = self.client.get('/admin/reports/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

        customer = get_user_model().objects.create_user(
            username='reports-customer',
            password=None,
        )
        self.client.force_login(customer)
        for url in (
            '/admin/reports/',
            reverse('admin_reports_export', args=('sales.csv',)),
        ):
            with self.subTest(url=url):
                self.assertIn(self.client.get(url).status_code, (302, 403))
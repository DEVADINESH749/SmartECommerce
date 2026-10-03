from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import Notification, Order, OrderItem, Payment, Product, User
from .workflows import OrderStatusTransitionError, update_order_status


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'email', 'role', 'active_status', 'created_at')
    search_fields = ('name', 'email')
    list_filter = ('role', 'is_active', 'created_at')
    ordering = ('-created_at', '-id')
    readonly_fields = ('created_at',)
    exclude = ('password_hash',)
    list_per_page = 50

    @admin.display(description='Active', boolean=True)
    def active_status(self, obj):
        return obj.is_active

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'category',
        'price',
        'stock',
        'popularity',
        'active_status',
        'created_at',
        'updated_at',
    )
    search_fields = ('name', 'category')
    list_filter = ('category', 'is_active')
    readonly_fields = ('created_at',)
    ordering = ('name',)
    list_per_page = 50

    @admin.display(description='Updated At')
    def updated_at(self, obj):
        return 'Not tracked by this table'

    @admin.display(description='Active', boolean=True)
    def active_status(self, obj):
        return obj.is_active


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    fields = ('product_name', 'unit_price', 'quantity', 'subtotal')
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user', 'total_amount', 'status', 'created_at', 'updated_at')
    search_fields = ('id', 'user__id', 'user__email')
    list_filter = ('status', 'created_at', 'updated_at')
    ordering = ('-created_at', '-id')
    readonly_fields = ('id', 'user', 'total_amount', 'stock_restored', 'created_at', 'updated_at')
    fields = ('id', 'user', 'total_amount', 'status', 'stock_restored', 'created_at', 'updated_at')
    inlines = (OrderItemInline,)
    list_per_page = 50

    @admin.display(description='Order ID')
    def order_id(self, obj):
        return obj.pk

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change:
            update_order_status(obj.pk, obj.status)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except OrderStatusTransitionError as error:
            self.message_user(request, error.detail, level=messages.ERROR)
            return HttpResponseRedirect(
                reverse('admin:catalog_admin_order_change', args=(object_id,))
            )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product_name', 'unit_price', 'quantity', 'subtotal')
    search_fields = ('product_name', 'order__id')
    ordering = ('order_id', 'id')
    readonly_fields = ('order', 'product', 'product_name', 'unit_price', 'quantity', 'subtotal')
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('catalog_admin.view_orderitem')

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'payment_id', 'order', 'user', 'amount', 'currency', 'status',
        'stripe_payment_intent_id', 'created_at', 'updated_at',
    )
    search_fields = ('id', 'order__id', 'user__id', 'stripe_payment_intent_id')
    list_filter = ('status', 'currency', 'created_at')
    ordering = ('-created_at', '-id')
    readonly_fields = (
        'id', 'order', 'user', 'amount', 'currency', 'status',
        'stripe_payment_intent_id', 'created_at', 'updated_at',
    )
    list_per_page = 50

    @admin.display(description='Payment ID')
    def payment_id(self, obj):
        return obj.pk

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('catalog_admin.view_payment')

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'type_display', 'message', 'read_status', 'created_at')
    search_fields = ('message', 'user__name', 'user__email')
    list_filter = ('notification_type', 'is_read', 'created_at')
    ordering = ('-created_at', '-id')
    readonly_fields = (
        'id', 'user', 'title', 'message', 'notification_type',
        'is_read', 'created_at', 'event_key',
    )
    list_per_page = 50

    @admin.display(description='Type')
    def type_display(self, obj):
        return obj.notification_type

    @admin.display(description='Read/Unread')
    def read_status(self, obj):
        return 'Read' if obj.is_read else 'Unread'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('catalog_admin.view_notification')

    def has_delete_permission(self, request, obj=None):
        return False
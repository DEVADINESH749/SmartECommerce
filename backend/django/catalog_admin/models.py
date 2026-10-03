from django.db import models
class User(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=255)
    password_hash = models.CharField(max_length=255)
    role = models.CharField(
        max_length=20,
        choices=(('customer', 'Customer'), ('staff', 'Staff'), ('admin', 'Admin')),
        default='customer',
    )
    is_active = models.BooleanField(null=True, default=True)
    created_at = models.DateTimeField(null=True)

    class Meta:
        managed = False
        db_table = 'users'
        ordering = ('email',)

    def __str__(self):
        return self.email


class Product(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    popularity = models.IntegerField(default=0)
    image = models.CharField(max_length=500, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'products'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Order(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    )

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, db_column='user_id', on_delete=models.DO_NOTHING)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    stock_restored = models.BooleanField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'orders'
        ordering = ('-created_at', '-id')

    def __str__(self):
        return f'Order #{self.pk}'


class OrderItem(models.Model):
    id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order, db_column='order_id', on_delete=models.DO_NOTHING)
    product = models.ForeignKey(Product, db_column='product_id', on_delete=models.DO_NOTHING)
    product_name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'order_items'

    def __str__(self):
        return f'{self.product_name} x {self.quantity}'


class Payment(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('SUCCEEDED', 'Succeeded'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    )

    id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order, db_column='order_id', on_delete=models.DO_NOTHING)
    user = models.ForeignKey(User, db_column='user_id', on_delete=models.DO_NOTHING)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    stripe_payment_intent_id = models.CharField(max_length=255, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'payments'
        ordering = ('-created_at', '-id')

    def __str__(self):
        return f'Payment #{self.pk}'


class Notification(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, db_column='user_id', on_delete=models.DO_NOTHING)
    title = models.CharField(max_length=120)
    message = models.CharField(max_length=500)
    notification_type = models.CharField(max_length=32)
    is_read = models.BooleanField()
    created_at = models.DateTimeField()
    event_key = models.CharField(max_length=255, null=True)

    class Meta:
        managed = False
        db_table = 'notifications'
        ordering = ('-created_at', '-id')

    def __str__(self):
        return f'{self.notification_type} for {self.user}'
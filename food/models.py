from django.db import models
import uuid
from django.utils import timezone
from datetime import timedelta
from django.utils.timezone import now

class Table(models.Model):
    table_number = models.IntegerField(unique=True)
    is_occupied = models.BooleanField(default=False)
    capacity = models.PositiveIntegerField(default=1)  # Number of seats

    def __str__(self):
        return f"Table {self.table_number} (Capacity: {self.capacity})"


class Dish(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(max_length=200)
    category = models.CharField(max_length=50, default="") #add
    type = models.CharField(max_length=50, default="") #add
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to="img", default="") #add

    def __str__(self):
        return self.name


class Order(models.Model):
    PENDING = 'Pending'
    FINISHED = 'Finished'

    ORDER_STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (FINISHED, 'Finished'),
    ]
    
    order_id = models.CharField(max_length=100, editable=False, unique=True, default=uuid.uuid4)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default=PENDING)
    created_time = models.DateTimeField(auto_now_add=True)
    updated_time = models.DateTimeField(auto_now=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    session_expired = models.BooleanField(default=False)
    table = models.ForeignKey(Table, related_name='orders', on_delete=models.CASCADE)
    num_customers = models.PositiveIntegerField(default=1)
    selected_package = models.CharField(max_length=255, blank=True, null=True)
    order_number = models.PositiveIntegerField(unique=True)

    class Meta:
        ordering = ['-created_time']

    def __str__(self):
        return f"Order No: {self.order_number} Order:ID {self.order_id} for Table {self.table.table_number} ({self.status})"
    
    @property
    def end_time(self):
        return self.created_time + timedelta(hours=2)

    def is_session_active(self):
        return now() < self.end_time
    
    def expire_session(self):
        if not self.is_session_active():
            self.status = self.FINISHED
            self.session_expired = True
            self.save()
            # Free the table
            self.table.is_occupied = False
            self.table.save()

    def save(self, *args, **kwargs):
        if not self.order_number:
            last_number = Order.objects.aggregate(models.Max('order_number'))['order_number__max'] or 0
            self.order_number = last_number + 1
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    PENDING = 'Pending'
    COOKING = 'Cooking'
    FINISHED = 'Finished'
    CANCELLED = 'Cancelled'

    ITEM_STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (COOKING, 'Cooking'),
        (FINISHED, 'Finished'),
        (CANCELLED, 'Cancelled'),
    ]

    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    dish = models.ForeignKey(Dish, related_name='order_items', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    additional_option = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=ITEM_STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.quantity} x {self.dish.name} (Options: {self.additional_option})"


class Invoice(models.Model):
    PENDING = 'Pending'
    PAID = 'Paid'
    CANCELLED = 'Cancelled'

    PAYMENT_STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (PAID, 'Paid'),
        (CANCELLED, 'Cancelled'),
    ]
    
    QR_CODE = 'QR Code'
    CASH = 'Cash'

    PAYMENT_METHOD_CHOICES = [
        (QR_CODE, 'QR Code'),
        (CASH, 'Cash'),
    ]

    invoice_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    order = models.OneToOneField(Order, related_name='invoice', on_delete=models.CASCADE)
    generated_at = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default=PENDING)
    selected_package = models.CharField(max_length=255, blank=True, null=True)  # Added field
    transaction_image = models.ImageField(upload_to='transaction_slips/', blank=True, null=True)  # <-- add this
    invoice_number = models.PositiveIntegerField(unique=True)

    def __str__(self):
        return f"Invoice No:{self.invoice_number} Invoice ID:{self.invoice_id} for Order No:{self.order.order_number} Order ID:{self.order.order_id} ({self.status})"
    
    def save(self, *args, **kwargs):
        if not self.invoice_number:
            last_number = Invoice.objects.aggregate(models.Max('invoice_number'))['invoice_number__max'] or 0
            self.invoice_number = last_number + 1
        super().save(*args, **kwargs)
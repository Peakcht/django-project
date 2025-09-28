from django.contrib import admin
from django.utils.html import format_html
from .models import Dish, Table, Order, OrderItem, Invoice
# Register your models here.

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        'invoice_number', 'order_number', 'generated_at', 'amount_paid',
        'payment_method', 'status', 'show_slip'
    ]
    list_filter = ['payment_method', 'status', 'generated_at']
    search_fields = ['invoice_number', 'order__order_number', 'reference_code']
    readonly_fields = ['invoice_number', 'order', 'generated_at', 'amount_paid']

    def order_number(self, obj):
        return obj.order.order_number
    order_number.short_description = 'Order Number'

    def show_slip(self, obj):
        if obj.transaction_image:
            return format_html('<img src="{}" width="60" style="border-radius:4px;" />', obj.transaction_image.url)
        return "-"
    show_slip.short_description = 'Slip'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # ❌ Prevent editing

    def has_delete_permission(self, request, obj=None):
        return False  # ❌ Prevent deleting

@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'type' , 'category')
    search_fields = ('name','type','category')
    list_filter = ('category','type')

class OrderItemInline(admin.TabularInline):  # Define this first
    model = OrderItem
    extra = 0  # no extra empty rows
    readonly_fields = ['dish', 'quantity', 'status', 'additional_option', 'created_at', 'updated_at']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'table', 'status', 'created_time', 'selected_package']
    search_fields = ['order_number',('status')]
    list_filter = ['status']
    inlines = [OrderItemInline]

    def has_change_permission(self, request, obj=None):
        return False  # ❌ Prevent editing

    def has_delete_permission(self, request, obj=None):
        return False  # ❌ Prevent deleting
    
    def has_add_permission(self, request):
        return False


#admin.site.register(Dish)
admin.site.register(Table)
#admin.site.register(OrderItem)
#admin.site.register(Order)
#admin.site.register(Invoice)

admin.site.site_header = "Shabu Cho Buffet Admin"
admin.site.site_title = "Admin Portal"
admin.site.index_title = "Welcome to Shabu Cho Buffet Admin"

import os
import qrcode
import uuid
import json
from datetime import datetime, timedelta
from django.shortcuts import render
from math import ceil
from .models import Table, Dish, Order, OrderItem, Invoice
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q, Count, Prefetch, Sum, Avg
from django.db.models.functions import ExtractWeekDay
from calendar import day_name
from collections import Counter
import calendar
from django.db.models.functions import TruncMonth
from django.urls import reverse
from django.conf import settings
from collections import defaultdict
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.contrib.auth.decorators import login_required

# Create your views here.

def order_status(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    order_items = order.items.all().order_by('updated_at')  # Orders items in sequence

    return render(request, 'order_status.html', {'order': order, 'order_items': order_items, 'hide_home': True,})


def order(request):
    # Retrieve dishes in the selected package
    dishes = Dish.objects.all()

    return render(request, 'order.html', {
        'dishes': dishes
    })

@login_required
def homepage(request):
    error = None
    qr_image_path = None
    group_order_id = None
    table_to_assign = None
    start_time = None
    end_time = None
    selected_package = None
    order = None  # <- Add this

    if request.method == 'POST':
        num_customers = request.POST.get('num_customers')
        selected_package = request.POST.get('package')

        request.session['selected_package'] = selected_package  # Store in session

        if not num_customers or not num_customers.isdigit():
            error = "Valid number of customers is required."
        else:
            num_customers = int(num_customers)
            available_tables = Table.objects.filter(is_occupied=False)

            for table in available_tables:
                if table.capacity >= num_customers:
                    table_to_assign = table
                    break

            if table_to_assign:
                table_to_assign.is_occupied = True
                table_to_assign.save()

                group_order_id = str(uuid.uuid4())
                start_time = datetime.now()
                end_time = start_time + timedelta(hours=2)

                # ✅ Pass request into QR generator
                qr_image_path = generate_qr_image(request, group_order_id)

                # ✅ Store order object in variable
                order = Order.objects.create(
                    table=table_to_assign,
                    order_id=group_order_id,
                    total_price=int(selected_package),
                    num_customers=num_customers,
                    selected_package=selected_package,
                )
            else:
                error = "No table available for the specified number of customers."

    else:
        selected_package = request.session.get('selected_package')
        num_customers = None  # <- Ensure defined in GET path too

    return render(request, 'homepage.html', {
        'error': error,
        'selected_package': selected_package,
        'qr_image_path': qr_image_path,
        'group_order_id': group_order_id,
        'table': table_to_assign,
        'start_time': start_time,
        'end_time': end_time,
        'order_number': order.order_number if order else None,  # <- Use order here
        'num_customers': num_customers,
    })

def generate_qr_image(request, group_order_id):
    # Build the full URL using the real host from the request
    relative_url = reverse('order_page', args=[group_order_id])
    order_page_url = request.build_absolute_uri(relative_url)

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(order_page_url)
    qr.make(fit=True)

    qr_image_relative_path = os.path.join('qrcodes', f'group_order_{group_order_id}.png')
    qr_image_path = os.path.join(settings.MEDIA_ROOT, qr_image_relative_path)

    os.makedirs(os.path.dirname(qr_image_path), exist_ok=True)
    qr_image = qr.make_image(fill_color="black", back_color="white")
    qr_image.save(qr_image_path)

    return os.path.join(settings.MEDIA_URL, qr_image_relative_path)

def session_expired_page(request):
    return render(request, 'session_expired.html')

def order_page(request, order_id):
    # Fetch the existing order
    order = get_object_or_404(Order, order_id=order_id)

    # Handle session expiration and finished status
    if not order.is_session_active() or order.status == Order.FINISHED:
        order.expire_session()
        return redirect('session_expired')

    # Use the selected_package from the Order, not the session
    selected_package = order.selected_package

    dishes = Dish.objects.filter(category=selected_package)

    return render(request, 'order_page.html', {
        'order': order,
        'dishes': dishes,
        'selected_package': selected_package,
        'end_time': order.end_time,
	'hide_home': True,
    })


#Try for Update All
def waiter_order(request):
    # Retrieve orders where at least one item is 'Ready to Serve'
    orders = Order.objects.prefetch_related(
        Prefetch(
            'items',
            queryset=OrderItem.objects.filter(status='Ready to Serve')
        )
    ).filter(
        items__status='Ready to Serve'
    ).distinct().order_by('table__table_number')

    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        order = get_object_or_404(Order, order_id=order_id)

        if 'bulk_finish' in request.POST:
            # Bulk finish all 'Ready to Serve' items
            items = order.items.filter(status='Ready to Serve')
            for item in items:
                item.status = 'Finished'
                item.save()
        else:
            # Individual finish
            item_id = request.POST.get('item_id')
            new_status = request.POST.get('new_status')
            order_item = get_object_or_404(OrderItem, id=item_id, order=order)

            if order_item.status == 'Ready to Serve' and new_status == 'Finished':
                order_item.status = new_status
                order_item.save()

        return redirect('waiter_order')

    return render(request, 'waiter_order.html', {'orders': orders})

# OG Update One-by-One
#def waiter_order(request):
    # Retrieve orders where at least one item is 'Ready to Serve'
    orders = Order.objects.prefetch_related(
        Prefetch(
            'items',
            queryset=OrderItem.objects.filter(status='Ready to Serve')
        )
    ).filter(
        items__status='Ready to Serve'
    ).distinct().order_by('table__table_number')

    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        item_id = request.POST.get('item_id')
        new_status = request.POST.get('new_status')

        order = get_object_or_404(Order, order_id=order_id)
        order_item = get_object_or_404(OrderItem, id=item_id, order=order)

        # Waiter can only update 'Ready to Serve' to 'Finished'
        if order_item.status == 'Ready to Serve' and new_status == 'Finished':
            order_item.status = new_status
            order_item.save()

        return redirect('waiter_order')

    return render(request, 'waiter_order.html', {'orders': orders})


def kitchen_order(request):
    # Step 1: Convert all 'Pending' items to 'Cooking' before rendering
    pending_items = OrderItem.objects.filter(status='Pending')
    for item in pending_items:
        item.status = 'Cooking'
        item.save()

    # Step 2: Query only orders that have 'Cooking' or 'Cancelled' items
    items_qs = OrderItem.objects.filter(status__in=['Cooking', 'Cancelled'])

    orders = Order.objects.prefetch_related(
        Prefetch('items', queryset=items_qs)
    ).filter(
        items__status__in=['Cooking', 'Cancelled']
    ).distinct().order_by('table__table_number')

    # Step 3: Handle POST requests (same as you already have)
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        new_status = request.POST.get('new_status')

        if 'item_id' in request.POST:
            item_id = request.POST.get('item_id')
            order_item = get_object_or_404(OrderItem, id=item_id, order__order_id=order_id)

            if order_item.status in ['Cooking'] and new_status in ['Cooking', 'Ready to Serve', 'Cancelled']:
                order_item.status = new_status
                order_item.save()

            order = order_item.order
            if not order.items.exclude(status__in=['Ready to Serve', 'Cancelled']).exists():
                order.status = "Pending"
                order.save()

        elif 'delete_item_id' in request.POST:
            delete_item_id = request.POST.get('delete_item_id')
            order_item = get_object_or_404(OrderItem, id=delete_item_id, order__order_id=order_id)
            if order_item.status == 'Cancelled':
                order_item.delete()

        else:
            order = get_object_or_404(Order, order_id=order_id)
            for item in order.items.filter(status='Cooking'):
                item.status = new_status
                item.save()

            if not order.items.exclude(status__in=['Ready to Serve', 'Cancelled']).exists():
                order.status = "Pending"
                order.save()

        return redirect('kitchen_order')

    return render(request, 'kitchen_order.html', {'orders': orders})

def submit_order(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data.'}, status=400)

        items = data.get('items', [])
        if not items:
            return JsonResponse({'success': False, 'error': 'No items in cart.'}, status=400)

        submitted_items = []
        for item in items:
            try:
                dish = Dish.objects.get(id=item['dishId'], category=order.selected_package)
                existing_item = OrderItem.objects.filter(order=order, dish=dish, status='Cancelled').first()
                if existing_item:
                    existing_item.status = OrderItem.PENDING
                    existing_item.quantity = item['quantity']
                    existing_item.additional_option = item.get('additional_option', '')
                    existing_item.save()
                    submitted_items.append(existing_item)
                else:
                    new_item = OrderItem.objects.create(
                        order=order,
                        dish=dish,
                        quantity=item['quantity'],
                        additional_option=item.get('additional_option', ''),
                        status=OrderItem.PENDING
                    )
                    submitted_items.append(new_item)
            except Dish.DoesNotExist:
                return JsonResponse({'success': False, 'error': f"Dish with ID {item['dishId']} not found."}, status=400)


        return JsonResponse({'success': True, 'order_id': order.order_id})

    submitted_items = order.items.filter(status=OrderItem.PENDING)
    return render(request, 'submit_order.html', {
        'order': order,
        'order_id': order_id,
        'submitted_items': submitted_items,
	'hide_home': True,
    })

def change_package(request, order_id):
    error = None

    # Fetch the order using the 'order_id'
    order = get_object_or_404(Order, order_id=order_id)

    if request.method == 'POST':
        # Get the selected package price from POST data
        package_price = request.POST.get('package')
        valid_packages = ['379']  # List of valid package prices

        if not package_price:
            error = "Package selection is required."
        elif package_price not in valid_packages:
            error = "Invalid package selected. Please try again."
        else:
            request.session['selected_package'] = package_price
            order.total_price = int(package_price)
            order.selected_package = package_price  # ✅ fix here
            order.save()
            return redirect('order_page', order_id=order.order_id)

            # Optionally clear current order items if the package changes dish options
            #order.items.all().delete()  # Optional, based on business logic
            
            # Save the updated order
            order.save()

            # Redirect to the order page with the updated order ID
            return redirect('order_page', order_id=order.order_id)

    return render(request, 'change_package.html', {
        'error': error,
        'selected_package': request.session.get('selected_package', None),
        'order': order,
	'hide_home': True,
    })

def checkout_list(request):
    """ Show all active orders with table numbers for staff to select """
    orders = Order.objects.filter(status='Pending').select_related('table')

    return render(request, 'checkout_list.html', {'orders': orders})

def checkout(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)

    # Group items by dish name and sum their quantities
    grouped_items = (
        order.items.values('dish__name', 'dish__price')
        .annotate(total_quantity=Sum('quantity'))
    )

    # Calculate adjusted total price
    adjusted_total_price = order.total_price * order.num_customers

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        amount_paid = adjusted_total_price

        status = 'Paid' if payment_method == 'Cash' else 'Pending'
        
        # Create invoice with Pending status
        invoice = Invoice.objects.create(
            order=order,
            payment_method=payment_method,
            amount_paid=amount_paid,
            status=status,
            selected_package=order.selected_package
        )

        order.status = 'Finished'
        order.table.is_occupied = False
        order.table.save()
        order.save()

        return redirect('checkout_list')

    return render(request, 'checkout.html', {
        'order': order,
        'grouped_items': grouped_items,
        'adjusted_total_price': adjusted_total_price
    })

def receipt(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    grouped_items = defaultdict(lambda: {"quantity": 0, "total_price": 0})

    for item in order.items.all():
        dish = item.dish
        grouped_items[dish]["quantity"] += item.quantity
        grouped_items[dish]["total_price"] += order.total_price

    # Convert to a list of tuples for template compatibility
    grouped_items = [(dish, details) for dish, details in grouped_items.items()]

    adjusted_total_price = order.total_price * order.num_customers

    context = {
        'order': order,
        'grouped_items': grouped_items,
        'adjusted_total_price': adjusted_total_price,
    }
    return render(request, 'receipt.html', context)


#def receipt_view(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    context = {
        'order': order,
        'order_items': order.items.all(),  # Access related OrderItems
    }
    return render(request, 'receipt.html', context)

def submit_receipt(request):
    search_query = request.GET.get('search')
    
    # Exclude paid invoices from the start
    invoices = Invoice.objects.select_related('order').exclude(status='Paid')

    if search_query:
        invoices = invoices.filter(
            Q(invoice_number__icontains=search_query)
        )

    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        transaction_image = request.FILES.get('transaction_image')
        reference_code = request.POST.get('reference_code')

        invoice = get_object_or_404(Invoice, order__order_id=order_id)

        if invoice.payment_method == "QR Code":
            invoice.reference_code = reference_code

        invoice.transaction_image = transaction_image
        invoice.status = Invoice.PAID
        invoice.save()

        return redirect('receipt_view', invoice_id=invoice.invoice_id)

    return render(request, 'submit_receipt.html', {'invoices': invoices})

def receipt_view(request, invoice_id):
    invoice = get_object_or_404(Invoice, invoice_id=invoice_id)
    return render(request, 'receipt_view.html', {'invoice': invoice})

def invoice_list_view(request):
    invoices = Invoice.objects.all().order_by('-generated_at')  # Sort newest first
    return render(request, 'invoice_list.html', {'invoices': invoices})

def dashboard(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    order_items = OrderItem.objects.select_related('order').all()
    invoices = Invoice.objects.select_related('order').filter(status=Invoice.PAID)

    try:
        if start_date and end_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            order_items = order_items.filter(order__created_time__date__range=[start_dt, end_dt])
            invoices = invoices.filter(generated_at__date__range=[start_dt, end_dt])
    except ValueError:
        start_date, end_date = None, None

    # Total sales (for summary or top 5)
    total_sales_data = (
        order_items.values('dish__name')
        .annotate(total_quantity=Sum('quantity'))
        .order_by('-total_quantity')
    )

    total_sales = {
        item["dish__name"]: item["total_quantity"]
        for item in total_sales_data
    }

    # Per-day dish sales data
    grouped_data = (
        order_items.values('dish__name', 'order__created_time__date')
        .annotate(total_quantity=Sum('quantity'))
        .order_by('order__created_time__date')
    )

    dish_datasets = {}
    all_dates = set()

    for item in grouped_data:
        name = item["dish__name"]
        date = item["order__created_time__date"].strftime("%Y-%m-%d")
        qty = item["total_quantity"]
        all_dates.add(date)

        if name not in dish_datasets:
            dish_datasets[name] = {
                "label": name,
                "by_date": {}
            }

        dish_datasets[name]["by_date"][date] = qty

    all_dates = sorted(all_dates)
    colors = ['#ff6384', '#36a2eb', '#ffce56', '#4bc0c0', '#9966ff', '#ff9f40']
    final_chart_data = []

    for i, dish in enumerate(dish_datasets.values()):
        aligned_data = [dish["by_date"].get(date, 0) for date in all_dates]
        final_chart_data.append({
            "label": dish["label"],
            "data": aligned_data,
            "dates": list(all_dates),
            "backgroundColor": colors[i % len(colors)],
            "borderColor": colors[i % len(colors)],
        })

    # Daily invoice totals (for chart)
    daily_invoice_totals = (
        invoices
        .annotate(date=TruncDate('generated_at'))
        .values('date')
        .annotate(total_sales=Sum('amount_paid'))
        .order_by('date')
    )

    # =========================
    # ✅ KPI CALCULATIONS
    # =========================

    # 1. Total Revenue
    total_revenue = invoices.aggregate(total=Sum('amount_paid'))['total'] or 0

    # 2. Most Popular Day
    popular_day_data = (
        invoices
        .annotate(day_of_week=TruncDate('generated_at'))
        .values('day_of_week')
        .annotate(total=Sum('amount_paid'))
        .order_by('-total')
        .first()
    )
    most_popular_day = popular_day_data['day_of_week'].strftime("%A") if popular_day_data else "N/A"

    # 3. Most Ordered Dish
    most_ordered_dish = total_sales_data[0]['dish__name'] if total_sales_data else "N/A"

    # 4. Average Order Value
    avg_order_value = invoices.aggregate(avg=Avg('amount_paid'))['avg'] or 0

    # Context
    context = {
        "chart_data": {"dish_datasets": final_chart_data},
        "total_sales": total_sales,
        "invoices": invoices,
        "daily_invoice_totals": list(daily_invoice_totals),
        "selected_start_date": start_date,
        "selected_end_date": end_date,

        # 🔵 KPI context
        "total_revenue": round(total_revenue, 2),
        "most_popular_day": most_popular_day,
        "most_ordered_dish": most_ordered_dish,
        "avg_order_value": round(avg_order_value, 2),
    }

    return render(request, 'dashboard.html', context)

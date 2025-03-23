from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('order_page/<str:order_id>/', views.order_page, name='order_page'),
    path('order/<str:order_id>/submit/', views.submit_order, name='submit_order'),
    path('order_status/<str:order_id>/', views.order_status, name='order_status'),
    path('change_package/<str:order_id>/', views.change_package, name='change_package'),
    path('kitchen_order/', views.kitchen_order, name='kitchen_order'),
    path('waiter_order/', views.waiter_order, name='waiter_order'),
    path('checkout_list/', views.checkout_list, name='checkout_list'), #add
    path('checkout/<str:order_id>/', views.checkout, name='checkout'),
    path('receipt/<str:order_id>/', views.receipt, name='receipt'), #checkout receipt
    path('submit_receipt/', views.submit_receipt, name='submit_receipt'),#submit transaction
    path('receipt_view/<uuid:invoice_id>/', views.receipt_view, name='receipt_view'), #use to view submit photo receipt
    path('invoice_list/', views.invoice_list_view, name='invoice_list'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('session_expired/', views.session_expired_page, name='session_expired'),
    #path('staff/', views.staff, name='dashboard-staff'),
    #path('product/', views.product, name='dashboard-product'),
    #path('order/', views.order, name='dashboard-order'),
]
if settings.DEBUG:  # Serve media files only in debug mode
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
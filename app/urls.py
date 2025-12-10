from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
from .views import logout_user

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_user, name='login'),
    path("logout/", logout_user, name="logout"),
    path('register/', views.register, name='register'),
    path('mpesa/callback/', views.mpesa_stk_callback, name='mpesa_callback'),
    path('export-csv/', views.export_csv, name='export_csv'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),


    #BORROWER REDIRECTS
    path("borrower/bnotifications/", views.bnotifications, name="bnotifications"),
    path("borrower/bsettings/", views.bsettings, name="bsettings"),
    path('borrower/', views.borrower, name='borrower'),
    path("borrower/apply-loan/", views.apply_loan, name="apply_loan"),
    path("borrower/my-loans/", views.my_loans, name="my_loans"),
    path("borrower/repay-loan/", views.repay_loan, name="repay_loan"),
    path("settings/update/", views.update_profile, name="update_profile"),
    path("settings/change-password/", views.change_password, name="change_password"),
    path("settings/notifications/", views.update_notifications, name="notification_settings"),
    path("settings/privacy/", views.update_privacy, name="privacy_settings"),
    path("settings/download-data/", views.download_my_data, name="download_my_data"),
    path("settings/delete-account/", views.delete_account, name="delete_account"),


    #LENDER REDIRECTS
    path("lender/lnotifications/", views.lnotifications, name="lnotifications"),
    path('lender/', views.lender, name='lender'),
    path("lender/loan-requests/", views.loan_requests, name="loan_requests"),
    path("lender/fund/<int:application_id>/", views.fund_loan, name="fund_loan"),
    path("lender/reject/<int:application_id>/", views.reject_loan, name="reject_loan"),
    path("lender/approve/", views.approved_loans, name="approved_loans"),
    path("lender/fund-wallet/", views.fund_wallet, name="fund_wallet"),
    path("lender/transactions/", views.transaction_history, name="transaction_history"),
    path("lender/lsettings/", views.lsettings_view, name="lsettings"),
    path("settings/lupdate/", views.lupdate_profile, name="lupdate_profile"),
    path("settings/lchange-password/", views.lchange_password, name="lchange_password"),
    path("settings/lnotifications/", views.lupdate_notifications, name="lnotification_settings"),
    path("settings/lprivacy/", views.lupdate_privacy, name="lprivacy_settings"),
    path("settings/ldownload-data/", views.ldownload_my_data, name="ldownload_my_data"),
    path("settings/ldelete-account/", views.ldelete_account, name="ldelete_account"),
]

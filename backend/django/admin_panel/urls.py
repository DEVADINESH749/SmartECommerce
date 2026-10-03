"""
URL configuration for admin_panel project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from catalog_admin.views import analytics_dashboard, reports_dashboard, reports_export

urlpatterns = [
    path(
        'admin/reports/export/<str:report_file>',
        admin.site.admin_view(reports_export),
        name='admin_reports_export',
    ),
    path(
        'admin/reports/',
        admin.site.admin_view(reports_dashboard),
        name='admin_reports',
    ),
    path(
        'admin/analytics/',
        admin.site.admin_view(analytics_dashboard),
        name='admin_analytics',
    ),
    path('admin/', admin.site.urls),
]

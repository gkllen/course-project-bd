from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "База знаний «Гай Ричи» — инженер знаний"
admin.site.site_title = "БЗ Гай Ричи"
admin.site.index_title = "Управление фактами и связями"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("portal.urls")),
]

handler404 = "portal.views.page_not_found"

from django.urls import path
from .views import (
    login_view, logout_view, dashboard, tarifas, abonados, buscar_vehiculo, 
    registrar_entrada, agregar_abonado, gestion_abonados, reimprimir_ticket,
    eliminar_abonado, renovar_abonado, generar_reporte
)
from . import views

urlpatterns = [
    path('login/', login_view, name='login'),
    path('', dashboard, name='dashboard'),
    path('logout/', logout_view, name='logout'),
    path('tarifas/', tarifas, name='tarifas'),
    path('abonados/', abonados, name='abonados'),
    
    path('buscar-vehiculo/', views.buscar_vehiculo, name='buscar_vehiculo'),
    path('procesar-salida/<int:registro_id>/', views.procesar_salida_vehiculo, name='procesar_salida_vehiculo'),
    path('reimprimir-ticket/<int:registro_id>/', views.reimprimir_ticket, name='reimprimir_ticket'),
    path('registrar_entrada/', registrar_entrada, name='registrar_entrada'),
    path('agregar_abonado/', agregar_abonado, name='agregar_abonado'),
    path('gestion_abonados/', gestion_abonados, name='gestion_abonados'),
    path('eliminar_abonado/<int:suscripcion_id>/', eliminar_abonado, name='eliminar_abonado'),
    path('renovar_abonado/<int:suscripcion_id>/', renovar_abonado, name='renovar_abonado'),
    path('generar-reporte/', generar_reporte, name='generar_reporte'),
]
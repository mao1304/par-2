from django.urls import path
from django.contrib.auth.views import LogoutView
from .views import login_view, dashboard, tarifas, abonados, buscar_vehiculo, registrar_entrada, agregar_abonado, gestion_abonados

urlpatterns = [
    path('login/', login_view, name='login'),
    path('', dashboard, name='dashboard'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('tarifas/', tarifas, name='tarifas'),
    path('abonados/', abonados, name='abonados'),
    path('buscar-vehiculo/', buscar_vehiculo, name='buscar_vehiculo'),
    path('registrar_entrada/', registrar_entrada, name='registrar_entrada'),
    path('agregar_abonado/', agregar_abonado, name='agregar_abonado'),
    path('gestion_abonados/', gestion_abonados, name='gestion_abonados'),
]
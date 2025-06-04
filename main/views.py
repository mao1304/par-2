from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')  # Redirigir a la página principal después del login
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            # Redirección basada en el rol del usuario
            if user.es_administrador():
                return redirect('admin_dashboard')
            else:
                return redirect('encargado_dashboard')
        else:
            messages.error(request, "Usuario o contraseña incorrectos")
            return render(request, 'login.html', {'error': True})
    
    return render(request, 'login.html')


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import RegistroParqueo, Vehiculo, Tarifa, SuscripcionMensual
from django.utils import timezone
from datetime import timedelta

@login_required
def dashboard(request):
    # Obtener estadísticas de vehículos
    total_carros = Vehiculo.objects.filter(tipo='carro').count()
    total_motos = Vehiculo.objects.filter(tipo='moto').count()
    total_vehiculos = total_carros + total_motos
    
    # Vehículos activos actualmente
    vehiculos_activos = RegistroParqueo.objects.filter(esta_activo=True).count()
    
    # Obtener ingresos
    hoy = timezone.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_mes = hoy.replace(day=1)
    
    ingresos_hoy = sum(
        r.valor_pagado for r in RegistroParqueo.objects.filter(
            fecha_salida__date=hoy,
            valor_pagado__isnull=False
        )
    ) or 0
    
    ingresos_semana = sum(
        r.valor_pagado for r in RegistroParqueo.objects.filter(
            fecha_salida__date__gte=inicio_semana,
            valor_pagado__isnull=False
        )
    ) or 0
    
    ingresos_mes = sum(
        r.valor_pagado for r in RegistroParqueo.objects.filter(
            fecha_salida__date__gte=inicio_mes,
            valor_pagado__isnull=False
        )
    ) or 0
    
    # Obtener tarifas actuales
    try:
        tarifa_carro = Tarifa.objects.get(tipo_vehiculo='carro').valor_por_hora
    except Tarifa.DoesNotExist:
        tarifa_carro = 0
    
    try:
        tarifa_moto = Tarifa.objects.get(tipo_vehiculo='moto').valor_por_hora
    except Tarifa.DoesNotExist:
        tarifa_moto = 0
    
    # Abonados (suscripciones activas)
    abonados_carros = SuscripcionMensual.objects.filter(
        vehiculo__tipo='carro',
        fecha_inicio__lte=timezone.now(),
        fecha_fin__gte=timezone.now()
    ).count()
    
    abonados_motos = SuscripcionMensual.objects.filter(
        vehiculo__tipo='moto',
        fecha_inicio__lte=timezone.now(),
        fecha_fin__gte=timezone.now()
    ).count()
    
    ingresos_mensuales = sum(
        s.monto_pagado for s in SuscripcionMensual.objects.filter(
            fecha_inicio__month=timezone.now().month,
            fecha_inicio__year=timezone.now().year
        )
    ) or 0

    context = {
        'total_carros': total_carros,
        'total_motos': total_motos,
        'total_vehiculos': total_vehiculos,
        'vehiculos_activos': vehiculos_activos,
        'ingresos_hoy': ingresos_hoy,
        'ingresos_semana': ingresos_semana,
        'ingresos_mes': ingresos_mes,
        'tarifa_carro': tarifa_carro,
        'tarifa_moto': tarifa_moto,
        'abonados_carros': abonados_carros,
        'abonados_motos': abonados_motos,
        'ingresos_mensuales': ingresos_mensuales,
        'es_admin': request.user.es_administrador(),
    }
    
    if request.user.es_administrador():
        return render(request, 'dashboard_admin.html', context)
    else:
        return render(request, 'dashboard_encargado.html', context)

@login_required
def tarifas(request):
    if not request.user.es_administrador():
        messages.error(request, "No tienes permiso para acceder a esta página")
        return redirect('dashboard')
    
    if request.method == 'POST':
        try:
            tarifa_carro = request.POST.get('tarifa_carro')
            tarifa_moto = request.POST.get('tarifa_moto')
            
            # Actualizar o crear tarifa para carros
            Tarifa.objects.update_or_create(
                tipo_vehiculo='carro',
                defaults={
                    'valor_por_hora': float(tarifa_carro),
                    'usuario_actualizacion': request.user
                }
            )
            
            # Actualizar o crear tarifa para motos
            Tarifa.objects.update_or_create(
                tipo_vehiculo='moto',
                defaults={
                    'valor_por_hora': float(tarifa_moto),
                    'usuario_actualizacion': request.user
                }
            )
            
            messages.success(request, "Tarifas actualizadas correctamente")
        except Exception as e:
            messages.error(request, f"Error al actualizar tarifas: {str(e)}")
    
    # Obtener tarifas actuales
    try:
        tarifa_carro = Tarifa.objects.get(tipo_vehiculo='carro').valor_por_hora
    except Tarifa.DoesNotExist:
        tarifa_carro = 0
    
    try:
        tarifa_moto = Tarifa.objects.get(tipo_vehiculo='moto').valor_por_hora
    except Tarifa.DoesNotExist:
        tarifa_moto = 0
    
    context = {
        'tarifa_carro': tarifa_carro,
        'tarifa_moto': tarifa_moto,
    }
    
    return render(request, 'tarifas.html', context)

@login_required
def abonados(request):
    pass

@login_required
def buscar_vehiculo(request):
    pass

@login_required
def registrar_entrada(request):
    if request.method == 'POST':
        try:
            placa = request.POST.get('placa').upper()
            tipo = request.POST.get('tipo')
            nombre = request.POST.get('nombre', '')

            # Verificar si el vehículo ya está registrado
            vehiculo, created = Vehiculo.objects.get_or_create(
                placa=placa,
                defaults={'tipo': tipo}
            )

            # Verificar si el vehículo ya tiene un registro activo
            if RegistroParqueo.objects.filter(vehiculo=vehiculo, esta_activo=True).exists():
                messages.error(request, "Este vehículo ya tiene un registro activo")
                return redirect('dashboard')

            # Crear nuevo registro de parqueo
            registro = RegistroParqueo.objects.create(
                vehiculo=vehiculo,
                usuario_registro=request.user
            )

            messages.success(request, f"Vehículo {placa} registrado exitosamente")
            return redirect('dashboard')

        except Exception as e:
            messages.error(request, f"Error al registrar vehículo: {str(e)}")
            return redirect('dashboard')

    return redirect('dashboard')

@login_required
def agregar_abonado(request):
    pass

@login_required
def gestion_vehiculos(request):
    pass

@login_required
def gestion_abonados(request):
    pass




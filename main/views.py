from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.urls import reverse
import win32ui
import win32print
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
            messages.success(request, f"Bienvenido, {user.username}")
            return redirect('dashboard')
        else:
            messages.error(request, "Usuario o contraseña incorrectos")
            return render(request, 'login.html', {'error': True})
    
    return render(request, 'login.html')

@login_required
def logout_view(request):
    """
    Vista personalizada para cerrar sesión
    """
    logout(request)
    messages.success(request, "Has cerrado sesión exitosamente")
    return redirect('login')

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import RegistroParqueo, Vehiculo, Tarifa, SuscripcionMensual, EstadisticaDiaria
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
    inicio_mes = hoy.replace(day=1)
    
    ingresos_hoy = sum(
        r.valor_pagado for r in RegistroParqueo.objects.filter(
            fecha_salida__date=hoy,
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
    
    # Obtener o crear tarifas con valores por defecto
    tarifa_carro_obj, _ = Tarifa.objects.get_or_create(
        tipo_vehiculo='carro',
        defaults={
            'valor_por_hora': 5000,
            'valor_estadia_larga': None,
            'usuario_actualizacion': request.user
        }
    )
    
    tarifa_moto_obj, _ = Tarifa.objects.get_or_create(
        tipo_vehiculo='moto',
        defaults={
            'valor_por_hora': 2000,
            'valor_estadia_larga': None,
            'usuario_actualizacion': request.user
        }
    )

    if request.method == 'POST':
        try:
            # Procesar datos del formulario
            tarifa_carro = request.POST.get('tarifa_carro')
            tarifa_moto = request.POST.get('tarifa_moto')
            tarifa_carro_larga = request.POST.get('tarifa_carro_larga')
            tarifa_moto_larga = request.POST.get('tarifa_moto_larga')
            
            # Actualizar tarifa para carros
            Tarifa.objects.update_or_create(
                tipo_vehiculo='carro',
                defaults={
                    'valor_por_hora': float(tarifa_carro),
                    'valor_estadia_larga': float(tarifa_carro_larga) if tarifa_carro_larga else None,
                    'usuario_actualizacion': request.user
                }
            )
            
            # Actualizar tarifa para motos
            Tarifa.objects.update_or_create(
                tipo_vehiculo='moto',
                defaults={
                    'valor_por_hora': float(tarifa_moto),
                    'valor_estadia_larga': float(tarifa_moto_larga) if tarifa_moto_larga else None,
                    'usuario_actualizacion': request.user
                }
            )
            
            messages.success(request, "Tarifas actualizadas correctamente")
            
            # Actualizar objetos para el contexto
            tarifa_carro_obj.refresh_from_db()
            tarifa_moto_obj.refresh_from_db()
            
        except ValueError:
            messages.error(request, "Por favor ingrese valores numéricos válidos")
        except Exception as e:
            messages.error(request, f"Error al actualizar tarifas: {str(e)}")
    
    context = {
        'tarifa_carro': {
            'valor_por_hora': tarifa_carro_obj.valor_por_hora,
            'valor_estadia_larga': tarifa_carro_obj.valor_estadia_larga,
        },
        'tarifa_moto': {
            'valor_por_hora': tarifa_moto_obj.valor_por_hora,
            'valor_estadia_larga': tarifa_moto_obj.valor_estadia_larga,
        },
    }
    
    return render(request, 'tarifas.html', context)
@login_required
def abonados(request):
    pass


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
import math

@login_required
def buscar_vehiculo(request):
    """
    Vista para buscar un vehículo por placa o código de barras
    Calcula el tiempo de estadía y el valor a pagar
    """
    vehiculo_info = None
    registro_activo = None
    tiempo_estadia = None
    horas_cobradas = None
    valor_a_pagar = None
    
    if request.method == 'GET' and 'placa' in request.GET:
        busqueda = request.GET.get('placa', '').strip().upper()
        
        if busqueda:
            try:
                # Buscar el registro activo por placa o código de barras
                registro_activo = RegistroParqueo.objects.filter(
                    Q(vehiculo__placa__iexact=busqueda) | Q(codigo_barras=busqueda),
                    esta_activo=True
                ).select_related('vehiculo').first()
                
                if registro_activo:
                    vehiculo_info = registro_activo.vehiculo
                    
                    # Calcular tiempo de estadía
                    tiempo_entrada = registro_activo.fecha_entrada
                    tiempo_actual = timezone.now()
                    tiempo_estadia = tiempo_actual - tiempo_entrada
                    
                    # Calcular horas (siempre redondeando hacia arriba)
                    horas_exactas = tiempo_estadia.total_seconds() / 3600
                    horas_cobradas = math.ceil(horas_exactas)
                    
                    # Usar el método del modelo para calcular el valor
                    valor_a_pagar = registro_activo.calcular_valor_estadia()
                    
                    if valor_a_pagar is None:
                        messages.error(request, f'No se encontró tarifa para vehículos tipo {vehiculo_info.tipo}')
                        valor_a_pagar = 0
                    
                    # Mensaje de éxito
                    messages.success(request, f'Vehículo encontrado: {vehiculo_info.placa}')
                    
                else:
                    # Buscar si existe el vehículo pero no tiene registro activo
                    vehiculo_existe = Vehiculo.objects.filter(placa__iexact=busqueda).first()
                    
                    if vehiculo_existe:
                        messages.warning(request, f'El vehículo {busqueda} existe pero no tiene un registro de entrada activo.')
                    else:
                        messages.error(request, f'No se encontró ningún vehículo con la placa o código: {busqueda}')
                        
            except Exception as e:
                messages.error(request, f'Error al buscar el vehículo: {str(e)}')
    
    # Obtener estadísticas para el dashboard
    context = {
        'vehiculo_info': vehiculo_info,
        'registro_activo': registro_activo,
        'tiempo_estadia': tiempo_estadia,
        'horas_cobradas': horas_cobradas,
        'valor_a_pagar': valor_a_pagar,
        'busqueda_realizada': 'placa' in request.GET,
        'termino_busqueda': request.GET.get('placa', ''),
        
        # Estadísticas adicionales para el contexto
        'total_vehiculos_activos': RegistroParqueo.objects.filter(esta_activo=True).count(),
        'ingresos_hoy': calcular_ingresos_hoy(),
    }
    
    return render(request, 'buscar_vehiculo.html', context)


def calcular_ingresos_hoy():
    """Función auxiliar para calcular ingresos del día actual"""
    from datetime import date
    hoy = date.today()
    registros_hoy = RegistroParqueo.objects.filter(
        fecha_salida__date=hoy,
        valor_pagado__isnull=False
    )
    return sum(registro.valor_pagado for registro in registros_hoy if registro.valor_pagado)


# Vista adicional para procesar la salida del vehículo
@login_required
def procesar_salida_vehiculo(request, registro_id):
    """
    Vista para procesar la salida de un vehículo
    """
    if request.method == 'POST':
        try:
            registro = get_object_or_404(RegistroParqueo, id=registro_id, esta_activo=True)
            
            # Verificar si el vehículo tiene membresía activa
            if registro.vehiculo.tiene_membresia_activa():
                messages.error(request, "Este vehículo tiene una membresía activa. No se puede registrar salida.")
                return redirect('dashboard')
            
            if registro.registrar_salida():
                # Actualizar estadísticas
                estadistica = EstadisticaDiaria.obtener_estadistica_dia()
                estadistica.actualizar_estadisticas(
                    tipo_vehiculo=registro.vehiculo.tipo,
                    monto=registro.valor_pagado
                )
                
                messages.success(request, 
                    f'Salida registrada exitosamente. '
                    f'Vehículo: {registro.vehiculo.placa} - '
                    f'Valor a pagar: ${registro.valor_pagado:,.2f}'
                )
            else:
                messages.error(request, 'Error al registrar la salida del vehículo.')
                
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return redirect('dashboard')


# Función auxiliar para formatear tiempo
def formatear_tiempo_estadia(tiempo_delta):
    """
    Formatea un timedelta a un string legible
    """
    if not tiempo_delta:
        return "0 minutos"
    
    total_seconds = int(tiempo_delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours} hora{'s' if hours != 1 else ''} y {minutes} minuto{'s' if minutes != 1 else ''}"
    else:
        return f"{minutes} minuto{'s' if minutes != 1 else ''}"

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

            # Verificar si el vehículo tiene membresía activa
            if vehiculo.tiene_membresia_activa():
                messages.error(request, "Este vehículo tiene una membresía activa. No se puede registrar entrada/salida.")
                return redirect('dashboard')

            # Verificar si el vehículo ya tiene un registro activo
            if vehiculo.tiene_registro_activo():
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
def gestion_vehiculos(request):
    pass

@login_required
def gestion_abonados(request):
    """
    Vista para gestionar los abonados (solo administrador)
    """
    if not request.user.es_administrador():
        messages.error(request, "No tienes permiso para acceder a esta página")
        return redirect('dashboard')
    
    # Obtener todas las suscripciones activas
    suscripciones_activas = SuscripcionMensual.objects.filter(
        fecha_fin__gte=timezone.now()
    ).select_related('vehiculo', 'usuario_registro').order_by('fecha_fin')
    
    # Obtener todas las suscripciones vencidas
    suscripciones_vencidas = SuscripcionMensual.objects.filter(
        fecha_fin__lt=timezone.now()
    ).select_related('vehiculo', 'usuario_registro').order_by('-fecha_fin')
    
    context = {
        'suscripciones_activas': suscripciones_activas,
        'suscripciones_vencidas': suscripciones_vencidas,
    }
    
    return render(request, 'gestion_abonados.html', context)

@login_required
def agregar_abonado(request):
    """
    Vista para agregar un nuevo abonado
    """
    if request.method == 'POST':
        try:
            placa = request.POST.get('placa').upper()
            tipo = request.POST.get('tipo')
            nombre = request.POST.get('nombre')
            telefono = request.POST.get('telefono')
            monto = float(request.POST.get('monto'))
            
            # Validar que el teléfono tenga 10 dígitos
            if not telefono.isdigit() or len(telefono) != 10:
                messages.error(request, 'El teléfono debe tener 10 dígitos numéricos')
                return redirect('dashboard')
            
            # Verificar si el vehículo existe
            vehiculo, created = Vehiculo.objects.get_or_create(
                placa=placa,
                defaults={'tipo': tipo}
            )
            
            # Verificar si ya tiene una membresía activa
            if vehiculo.tiene_membresia_activa():
                messages.error(request, f'El vehículo {placa} ya tiene una membresía activa')
                return redirect('dashboard')
            
            # Verificar si tiene un registro activo
            if vehiculo.tiene_registro_activo():
                messages.error(request, f'El vehículo {placa} tiene un registro de entrada activo. Debe registrar la salida antes de crear la membresía.')
                return redirect('dashboard')
            
            # Calcular fecha de fin (1 mes desde ahora)
            fecha_inicio = timezone.now()
            fecha_fin = fecha_inicio + timedelta(days=30)
            
            # Crear la suscripción
            suscripcion = SuscripcionMensual.objects.create(
                vehiculo=vehiculo,
                nombre_cliente=nombre,
                telefono_cliente=telefono,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                monto_pagado=monto,
                usuario_registro=request.user
            )
            
            # Actualizar estadísticas
            estadistica = EstadisticaDiaria.obtener_estadistica_dia()
            estadistica.actualizar_estadisticas(
                tipo_vehiculo=tipo,
                monto=monto,
                es_membresia=True
            )
            
            messages.success(request, f'Membresía creada exitosamente para el vehículo {placa}')
            
        except Exception as e:
            messages.error(request, f'Error al crear la membresía: {str(e)}')
    
    return redirect('dashboard')

@login_required
def eliminar_abonado(request, suscripcion_id):
    """
    Vista para eliminar una suscripción (solo administrador)
    """
    if not request.user.es_administrador():
        messages.error(request, "No tienes permiso para realizar esta acción")
        return redirect('dashboard')
    
    try:
        suscripcion = get_object_or_404(SuscripcionMensual, id=suscripcion_id)
        placa = suscripcion.vehiculo.placa
        suscripcion.delete()
        messages.success(request, f'Membresía eliminada exitosamente para el vehículo {placa}')
    except Exception as e:
        messages.error(request, f'Error al eliminar la membresía: {str(e)}')
    
    return redirect('gestion_abonados')

@login_required
def renovar_abonado(request, suscripcion_id):
    """
    Vista para renovar una suscripción (solo administrador)
    """
    if not request.user.es_administrador():
        messages.error(request, "No tienes permiso para realizar esta acción")
        return redirect('dashboard')
    
    if request.method == 'POST':
        try:
            suscripcion = get_object_or_404(SuscripcionMensual, id=suscripcion_id)
            monto = float(request.POST.get('monto'))
            
            # Actualizar la suscripción
            suscripcion.fecha_inicio = timezone.now()
            suscripcion.fecha_fin = suscripcion.fecha_inicio + timedelta(days=30)
            suscripcion.monto_pagado = monto
            suscripcion.usuario_registro = request.user
            suscripcion.save()
            
            messages.success(request, f'Membresía renovada exitosamente para el vehículo {suscripcion.vehiculo.placa}')
            
        except Exception as e:
            messages.error(request, f'Error al renovar la membresía: {str(e)}')
    
    return redirect('gestion_abonados')

@login_required
def reimprimir_ticket(request, registro_id):
    """
    Vista para reimprimir el ticket de ingreso
    """
    try:
        registro = get_object_or_404(RegistroParqueo, id=registro_id)
        if registro.imprimir_ticket_ingreso():
            messages.success(request, 'Ticket reimpreso exitosamente')
        else:
            messages.error(request, 'Error al reimprimir el ticket')
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    # Redirigir de vuelta a la búsqueda con la placa del vehículo
    return redirect(f"{reverse('buscar_vehiculo')}?placa={registro.vehiculo.placa}")

@login_required
def generar_reporte(request):
    """
    Vista para generar el reporte diario
    """
    if not request.user.es_administrador():
        messages.error(request, "No tienes permiso para acceder a esta página")
        return redirect('dashboard')
    
    try:
        estadistica = EstadisticaDiaria.obtener_estadistica_dia()
        
        # Crear el contenido del reporte
        fecha = timezone.now().strftime('%Y-%m-%d %H:%M')
        total_vehiculos = estadistica.total_carros + estadistica.total_motos
        total_ingresos = estadistica.total_ingresos + estadistica.ingresos_membresias
        
        reporte = f"""
    P
    
    PARQUEADERO PARKAUTOS
    
    REPORTE DIARIO
    
    Fecha: {fecha}
    
    RESUMEN DEL DÍA
    
    Total Vehículos: {total_vehiculos}
    - Carros: {estadistica.total_carros}
    - Motos: {estadistica.total_motos}
    
    Ingresos por Parqueo: ${estadistica.total_ingresos:,.2f}
    Ingresos por Membresías: ${estadistica.ingresos_membresias:,.2f}
    Total Ingresos: ${total_ingresos:,.2f}
    
    Membresías Vendidas: {estadistica.total_membresias}
    
    www.sap-parking.com
    """
        
        # Imprimir el reporte
        printer_name = "POS-80"
        pdc = win32ui.CreateDC()
        pdc.CreatePrinterDC(printer_name)
        pdc.StartDoc("Reporte Diario")
        pdc.StartPage()
        
        font = win32ui.CreateFont({
            "name": "Courier New",
            "height": 20,
            "weight": 400,
        })
        pdc.SelectObject(font)
        
        lineas = reporte.strip().split("\n")
        x_center = pdc.GetDeviceCaps(8) // 2
        y = 50
        
        for linea in lineas:
            linea = linea.strip()
            if not linea:
                y += 20
                continue
                
            text_size = pdc.GetTextExtent(linea)
            x = x_center - (text_size[0] // 2)
            pdc.TextOut(x, y, linea)
            y += 30
        
        pdc.EndPage()
        pdc.EndDoc()
        pdc.DeleteDC()
        
        # Comando de corte
        cut_command = b'\x1D\x56\x00'
        hprinter = win32print.OpenPrinter(printer_name)
        try:
            hjob = win32print.StartDocPrinter(hprinter, 1, ("Corte de papel", None, "RAW"))
            win32print.StartPagePrinter(hprinter)
            win32print.WritePrinter(hprinter, cut_command)
            win32print.EndPagePrinter(hprinter)
            win32print.EndDocPrinter(hprinter)
        finally:
            win32print.ClosePrinter(hprinter)
        
        messages.success(request, 'Reporte generado e impreso exitosamente')
        
    except Exception as e:
        messages.error(request, f'Error al generar el reporte: {str(e)}')
    
    return redirect('dashboard')



from django.shortcuts import render
from django.utils import timezone
from .models import Vehiculo, RegistroParqueo

def vehiculos_con_entrada_activa(request):
    """
    Vista que muestra únicamente los vehículos que están dentro del parqueadero
    pero NO tienen membresía activa (deben pagar por horas)
    """
    
    # Obtener todos los vehículos que tienen al menos un registro activo
    # pero que NO tienen una suscripción mensual activa
    vehiculos_sin_membresia = Vehiculo.objects.filter(
        registros__esta_activo=True
    ).exclude(
        # Excluir vehículos con suscripción activa
        suscripciones__fecha_inicio__lte=timezone.now(),
        suscripciones__fecha_fin__gte=timezone.now()
    ).distinct()
    
    # Para cada vehículo, obtener su último registro activo y calcular información
    vehiculos_con_info = []
    total_carros = 0
    total_motos = 0
    total_estimado = 0
    
    for vehiculo in vehiculos_sin_membresia:
        # Obtener el último registro activo
        ultimo_registro = vehiculo.registros.filter(esta_activo=True).latest('fecha_entrada')
        
        # Calcular tiempo estacionado
        tiempo_estacionado = timezone.now() - ultimo_registro.fecha_entrada
        
        # Calcular horas y minutos
        segundos_totales = int(tiempo_estacionado.total_seconds())
        horas = segundos_totales // 3600
        minutos = (segundos_totales % 3600) // 60
        
        # Calcular valor estimado usando el mismo método del modelo
        valor_estimado = ultimo_registro.calcular_valor_estadia()
        
        # Contar por tipo
        if vehiculo.tipo == 'carro':
            total_carros += 1
        else:
            total_motos += 1
            
        if valor_estimado:
            total_estimado += valor_estimado
        
        vehiculos_con_info.append({
            'vehiculo': vehiculo,
            'ultimo_registro': ultimo_registro,
            'horas': horas,
            'minutos': minutos,
            'valor_estimado': valor_estimado,
        })
    
    # Ordenar por tiempo de entrada (más recientes primero)
    vehiculos_con_info.sort(key=lambda x: x['ultimo_registro'].fecha_entrada, reverse=True)
    
    context = {
        'vehiculos': vehiculos_con_info,
        'fecha_actual': timezone.now(),
        'total_carros': total_carros,
        'total_motos': total_motos,
        'total_estimado': total_estimado,
    }
    
    return render(request, 'vehiculos_activos.html', context)
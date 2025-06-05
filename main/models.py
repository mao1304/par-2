import math
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid
import qrcode
from io import BytesIO
from django.core.files import File
import os
import barcode
from barcode.writer import ImageWriter
import win32print
import win32ui
import win32con
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageWin

class Usuario(AbstractUser):
    ROLES = (
        ('admin', 'Administrador'),
        ('encargado', 'Encargado'),
    )
    rol = models.CharField(max_length=10, choices=ROLES)
    
    # Resolviendo conflictos de related_name
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='usuario_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='usuario_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )
    
    def __str__(self):
        return f"{self.username} - {self.rol}"

    def es_administrador(self):
        return self.rol == 'admin'
    
    def es_encargado(self):
        return self.rol == 'encargado'


class Vehiculo(models.Model):
    TIPOS_VEHICULO = (
        ('carro', 'Carro'),
        ('moto', 'Moto'),
    )
    
    placa = models.CharField(max_length=10, unique=True, db_index=True)
    tipo = models.CharField(max_length=10, choices=TIPOS_VEHICULO)
    
    class Meta:
        verbose_name = "Vehículo"
        verbose_name_plural = "Vehículos"
    
    def __str__(self):
        return f"{self.placa} - {self.get_tipo_display()}"

    def tiene_membresia_activa(self):
        """Verifica si el vehículo tiene una suscripción mensual activa"""
        ahora = timezone.now()
        return self.suscripciones.filter(
            fecha_fin__gte=ahora,
            fecha_inicio__lte=ahora
        ).exists()


class RegistroParqueo(models.Model):
    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.CASCADE, related_name='registros')
    fecha_entrada = models.DateTimeField(default=timezone.now)
    fecha_salida = models.DateTimeField(null=True, blank=True)
    esta_activo = models.BooleanField(default=True)
    valor_pagado = models.FloatField(null=True, blank=True)
    codigo_barras = models.CharField(max_length=100, unique=True, null=True, blank=True)
    imagen_codigo_barras = models.ImageField(upload_to='codigos_barras/', null=True, blank=True)
    usuario_registro = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-fecha_entrada']
        verbose_name = "Registro de Parqueo"
        verbose_name_plural = "Registros de Parqueo"
    
    def __str__(self):
        return f"{self.vehiculo.placa} - Entrada: {self.fecha_entrada.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        es_nuevo = self._state.adding  # Detectar si es nuevo antes de guardar

        if not self.pk or not self.codigo_barras:
            self.generar_codigo_barras()

        super().save(*args, **kwargs)

        if es_nuevo:
            self.imprimir_ticket_ingreso()

    def generar_codigo_barras(self):
        """
        Genera un código de barras CODE128 con formato mejorado y texto bien posicionado
        """
        try:
            # Generar código único usando placa y timestamp
            timestamp = int(timezone.now().timestamp())
            codigo = f"{timestamp}"
            self.codigo_barras = codigo
            
            # Configuración optimizada del código de barras
            code = barcode.get('code128', codigo, writer=ImageWriter())
            
            # Opciones para la generación de la imagen
            options = {
                'format': 'PNG',
                'module_width': 0.35,     # Ancho de cada barra
                'module_height': 25,      # Altura de las barras
                'quiet_zone': 10,         # Margen alrededor
                'font_size': 16,           # Desactivar texto automático
                'background': 'white',    # Fondo blanco
                'foreground': 'black',    # Barras negras
                'dpi': 300,               # Alta resolución
            }
            
            # Generar imagen en memoria
            buffer = BytesIO()
            code.write(buffer, options)
            buffer.seek(0)
            
            # Procesamiento adicional con PIL para mejor control
            img = Image.open(buffer)
            draw = ImageDraw.Draw(img)
            
            # Configurar fuente (intentar Arial, fallback a fuente default)
            try:
                font = ImageFont.truetype("arial.ttf", 16)
            except:
                font = ImageFont.load_default()
            
            # Texto a mostrar (usamos solo la placa)
            text = self.vehiculo.placa
            text_width = draw.textlength(text, font=font)
            
            # Calcular posición (centrado en la parte inferior)
            text_position = ((img.width - text_width) / 2, img.height - 25)
            
            # Dibujar texto
            draw.text(text_position, text, font=font, fill="black")
            
            # Guardar la imagen final
            final_buffer = BytesIO()
            img.save(final_buffer, format='PNG')
            final_buffer.seek(0)
            
            # Nombre del archivo
            filename = f'barcode_{self.vehiculo.placa}_{timestamp}.png'
            
            # Guardar en el campo de imagen
            self.imagen_codigo_barras.save(filename, File(final_buffer), save=False)
            
        except Exception as e:
            print(f"Error generando código de barras: {e}")
            raise

    def calcular_valor_estadia(self):
        """Calcula el valor a pagar por el tiempo estacionado (se cobra cada hora completa)"""
        if self.fecha_salida and self.fecha_entrada:
            tiempo_estacionado = self.fecha_salida - self.fecha_entrada
            horas = tiempo_estacionado.total_seconds() / 3600
            horas_cobradas = math.ceil(horas)  # Redondea hacia arriba

            try:
                tarifa = Tarifa.objects.get(tipo_vehiculo=self.vehiculo.tipo)
                return round(horas_cobradas * float(tarifa.valor_por_hora), 2)
            except Tarifa.DoesNotExist:
                return None
        return None

    def registrar_salida(self):
        """Método para registrar la salida del vehículo"""
        if not self.fecha_salida:
            self.fecha_salida = timezone.now()
            self.esta_activo = False
            self.valor_pagado = self.calcular_valor_estadia()
            self.save()
            return True
        return False

    def imprimir_ticket_ingreso(self):
        print("registrar_salida va a imprimir el ticket")
        """Imprime el ticket de ingreso del vehículo con formato similar al ejemplo"""
        try:
            printer_name = "POS-80"

            # Obtener tarifas del modelo Tarifa
            try:
                tarifa_carro = Tarifa.objects.get(tipo_vehiculo='carro')
                valor_carro = f"${tarifa_carro.valor_por_hora:,.0f}"
            except Tarifa.DoesNotExist:
                valor_carro = "No definida"

            try:
                tarifa_moto = Tarifa.objects.get(tipo_vehiculo='moto')
                valor_moto = f"${tarifa_moto.valor_por_hora:,.0f}"
            except Tarifa.DoesNotExist:
                valor_moto = "No definida"

            # Crear el contenido del ticket (formato similar al ejemplo)
            fecha_entrada = self.fecha_entrada.strftime('%I:%M %p %Y-%m-%d').upper()
            placa = self.vehiculo.placa
            tipo = "AUTOMOVIL-CAMIONETA" if self.vehiculo.tipo == 'carro' else "MOTOCICLETA"

            ticket = f"""
    P
    
    PARQUEADERO PARKAUTOS
    
    NIT:12345678-9
    
    NO RESPONSABLE DE IVA
    
    CALLE 72#3.26 CENTRO
    
    TELEFONO:8924988
    
    HORARIO:6:00 AM A 9:00 PM
    
    Recibo No:12,345
    
    Placa:{placa}
    
    Tarifa:
    {tipo}
    
    Entrada:
    {fecha_entrada}
    
    Cajero:
    MAURICIO ALVAREZ
    
    REGLAMENTO
    * El vehiculo se entregara al portador del recibo
    * No aceptamos ordenes telefónicas ni escritas
    * Retirado el vehiculo no aceptamos reclamos
    * No respondemos por objetos dejados en el vehiculo
    * No respondemos por daños al vehiculo causados por terceros
    * No respondemos por pérdida, daños o hurtos ocurridos como
        consecuencia de incendio, terremoto o otros actos de fuerza mayor
    
    www.sap-parking.com
    """

            # Iniciar impresión
            pdc = win32ui.CreateDC()
            pdc.CreatePrinterDC(printer_name)
            pdc.StartDoc("Ticket de Ingreso")
            pdc.StartPage()

            font = win32ui.CreateFont({
                "name": "Courier New",  # Fuente de ancho fijo para mejor alineación
                "height": 20,          # Tamaño un poco más pequeño
                "weight": 400,         # Peso normal
            })
            pdc.SelectObject(font)

            lineas = ticket.strip().split("\n")
            x_center = pdc.GetDeviceCaps(8) // 2
            y = 50  # Posición inicial más arriba

            for linea in lineas:
                # Eliminar espacios en blanco al inicio y final
                linea = linea.strip()
                
                # Si la línea está vacía, solo avanzamos el cursor
                if not linea:
                    y += 20
                    continue
                    
                text_size = pdc.GetTextExtent(linea)
                x = x_center - (text_size[0] // 2)
                pdc.TextOut(x, y, linea)
                y += 30  # Espaciado entre líneas

            # Imprimir código de barras
            if self.imagen_codigo_barras:
                try:
                    img_path = self.imagen_codigo_barras.path
                    if os.path.exists(img_path):
                        img = Image.open(img_path)
                        img = img.convert("1")
                        width = 300  # Ancho un poco más pequeño
                        ratio = width / float(img.size[0])
                        height = int(float(img.size[1]) * float(ratio))
                        img = img.resize((width, height), Image.LANCZOS)
                        dib = ImageWin.Dib(img)
                        dib.draw(pdc.GetHandleOutput(), (
                            x_center - img.size[0] // 2,
                            y + 20,  # Espacio antes del código de barras
                            x_center + img.size[0] // 2,
                            y + 20 + img.size[1]
                        ))
                        y += img.size[1] + 40  # Espacio después del código de barras
                except Exception as img_error:
                    print(f"Error al imprimir imagen del código de barras: {img_error}")
                    pdc.TextOut(x_center - 50, y, f"Código: {self.codigo_barras}")
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

            return True
        except Exception as e:
            print(f"Error al imprimir ticket: {e}")
            return False

class SuscripcionMensual(models.Model):
    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.CASCADE, related_name='suscripciones')
    nombre_cliente = models.CharField(max_length=100)
    telefono_cliente = models.CharField(max_length=100)
    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_fin = models.DateTimeField()
    monto_pagado = models.FloatField()
    usuario_registro = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"Suscripción {self.nombre_cliente} - {self.vehiculo.placa}"

    def esta_activa(self):
        ahora = timezone.now()
        return self.fecha_inicio <= ahora <= self.fecha_fin


class Tarifa(models.Model):
    """Modelo para las tarifas del parqueadero"""
    TIPOS = (
        ('carro', 'Carro'),
        ('moto', 'Moto'),
    )
    tipo_vehiculo = models.CharField(max_length=10, choices=TIPOS, unique=True)
    valor_por_hora = models.FloatField()
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    usuario_actualizacion = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Tarifa"
        verbose_name_plural = "Tarifas"
    
    def __str__(self):
        return f"Tarifa {self.tipo_vehiculo}: ${self.valor_por_hora}/hora"

class EstadisticaDiaria(models.Model):
    fecha = models.DateField(auto_now_add=True)
    total_ingresos = models.FloatField(default=0)
    total_carros = models.IntegerField(default=0)
    total_motos = models.IntegerField(default=0)
    total_membresias = models.IntegerField(default=0)
    ingresos_membresias = models.FloatField(default=0)
    
    class Meta:
        verbose_name = "Estadística Diaria"
        verbose_name_plural = "Estadísticas Diarias"
    
    def __str__(self):
        return f"Estadísticas del {self.fecha}"
    
    @classmethod
    def obtener_estadistica_dia(cls):
        """Obtiene o crea la estadística del día actual"""
        hoy = timezone.now().date()
        estadistica, created = cls.objects.get_or_create(fecha=hoy)
        return estadistica
    
    def actualizar_estadisticas(self, tipo_vehiculo, monto=0, es_membresia=False):
        """Actualiza las estadísticas con un nuevo registro"""
        if tipo_vehiculo == 'carro':
            self.total_carros += 1
        elif tipo_vehiculo == 'moto':
            self.total_motos += 1
            
        if es_membresia:
            self.total_membresias += 1
            self.ingresos_membresias += monto
        else:
            self.total_ingresos += monto
            
        self.save()
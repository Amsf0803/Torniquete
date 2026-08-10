# 🏫 Torniquete - Sistema de Acceso Automatizado

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![C](https://img.shields.io/badge/C-00599C?style=for-the-badge&logo=c&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-005C84?style=for-the-badge&logo=mysql&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-323330?style=for-the-badge&logo=javascript&logoColor=F7DF1E)

Un sistema de control de acceso escolar inteligente y eficiente. Este proyecto automatiza la gestión de entradas mediante la integración de credenciales institucionales y la validación de horarios académicos en tiempo real.

## ✨ Características Principales

- **Integración DAE y SAES:** Validación instantánea de credenciales y cruce de datos con los horarios oficiales de los estudiantes para permitir o denegar el acceso.
- **Control de Hardware Físico:** Uso de microcontroladores programados para la lectura de tarjetas y el accionamiento de los mecanismos del torniquete.
- **Seguimiento de Entradas Diario:** El esquema de la base de datos cuenta con funciones de reinicio automatizado para llevar un control exacto de los accesos por día.
- **Módulo de Administración:** Un panel dedicado para la supervisión del sistema, gestión de usuarios y revisión de registros.
- **Arquitectura Escalable:** Separación clara entre la lógica del servidor de acceso, el hardware físico y la administración del sistema.

## 🛠️ Tecnologías Utilizadas

- **Hardware / Microcontroladores:** C (Para la lectura de credenciales y control del mecanismo).
- **Backend:** Python
- **Base de Datos:** MySQL
- **Frontend:** HTML, CSS, JavaScript puro para una interfaz ligera y rápida.

## 📁 Estructura del Proyecto

El núcleo del sistema se divide en diferentes módulos para mantener el código estructurado y seguro:

- `server.py`: Gestiona la lógica principal del torniquete, atiende las peticiones de validación, verifica los horarios del SAES y registra los accesos en la base de datos.
- `admin.py`: Maneja el panel de control para administradores, permitiendo visualizar estadísticas, gestionar credenciales y auditar el sistema.
- Código en `C`: Lógica embebida en la placa/microcontrolador para interactuar directamente con los sensores, lectores RFID y el hardware del torniquete.

## 🚀 Requisitos Previos

Antes de ejecutar el proyecto, asegúrate de tener instalado:

- Python 3.8+
- Servidor MySQL en ejecución
- Entorno virtual de Python (recomendado)
- Entorno de desarrollo para compilar y cargar el código en C (ej. Arduino IDE, PlatformIO, o toolchain específico).

## ⚙️ Instalación y Configuración

**1. Clonar el repositorio**

```bash
git clone [https://github.com/tu-usuario/torniquete.git](https://github.com/tu-usuario/torniquete.git)
cd torniquete
```

**2. Crear y activar un entorno virtual (Opcional pero recomendado)**

```bash
python -m venv env
source env/bin/activate  # En sistemas basados en Linux como Arch o Ubuntu
```

**3. Instalar las dependencias**

```bash
pip install -r requirements.txt
```

**4. Configurar la Base de Datos**

- Crea una base de datos en MySQL.
- Importa el esquema inicial (asegúrate de que los eventos de reinicio diario estén habilitados en tu servidor MySQL).
- Configura tus credenciales de base de datos en un archivo `.env` o en el archivo de configuración correspondiente.

**5. Flashear el Microcontrolador**

- Abre el código fuente en C con tu entorno de desarrollo.
- Verifica los pines de conexión y compila/sube el código a tu placa para que pueda comunicarse con el servidor.

**6. Ejecutar los servicios**
Para iniciar el sistema de validación:

```bash
python server.py
```

Para iniciar el panel de administración:

```bash
python admin.py
```

## 🤝 Contribución

Si deseas contribuir a este proyecto, por favor crea un _fork_ del repositorio, crea una nueva rama para tus cambios y envía un _Pull Request_. Toda mejora a la lógica de validación, la programación del hardware o a la interfaz gráfica es bienvenida.

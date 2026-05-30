# 🏫 Torniquete - Sistema de Acceso Automatizado

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-005C84?style=for-the-badge&logo=mysql&logoColor=white)
![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-323330?style=for-the-badge&logo=javascript&logoColor=F7DF1E)

Un sistema de control de acceso escolar inteligente y eficiente. Este proyecto automatiza la gestión de entradas mediante la integración de credenciales institucionales y la validación de horarios académicos en tiempo real.

## ✨ Características Principales

* **Integración DAE y SAES:** Validación instantánea de credenciales y cruce de datos con los horarios oficiales de los estudiantes para permitir o denegar el acceso.
* **Seguimiento de Entradas Diario:** El esquema de la base de datos cuenta con funciones de reinicio automatizado para llevar un control exacto de los accesos por día.
* **Módulo de Administración:** Un panel dedicado para la supervisión del sistema, gestión de usuarios y revisión de registros.
* **Arquitectura Escalable:** Separación clara entre la lógica del servidor de acceso y la administración del sistema.

## 🛠️ Tecnologías Utilizadas

* **Backend:** Python
* **Base de Datos:** MySQL
* **Frontend:** HTML, CSS, JavaScript puro para una interfaz ligera y rápida.

## 📁 Estructura del Proyecto

El núcleo del sistema se divide en dos scripts principales para mantener el código modular y seguro:

* `server.py`: Gestiona la lógica principal del torniquete, atiende las peticiones de validación, verifica los horarios del SAES y registra los accesos en la base de datos.
* `admin.py`: Maneja el panel de control para administradores, permitiendo visualizar estadísticas, gestionar credenciales y auditar el sistema.

## 🚀 Requisitos Previos

Antes de ejecutar el proyecto, asegúrate de tener instalado:
* Python 3.8+
* Servidor MySQL en ejecución
* Entorno virtual de Python (recomendado)

## ⚙️ Instalación y Configuración

**1. Clonar el repositorio**
```bash
git clone [https://github.com/tu-usuario/torniquete.git](https://github.com/tu-usuario/torniquete.git)
cd torniquete

2. Crear y activar un entorno virtual (Opcional pero recomendado)
Bash

python -m venv env
source env/bin/activate  # En sistemas basados en Linux

3. Instalar las dependencias
Bash

pip install -r requirements.txt

4. Configurar la Base de Datos

    Crea una base de datos en MySQL.

    Importa el esquema inicial (asegúrate de que los eventos de reinicio diario estén habilitados en tu servidor MySQL).

    Configura tus credenciales de base de datos en un archivo .env o en el archivo de configuración correspondiente.

5. Ejecutar los servicios
Para iniciar el sistema de acceso:
Bash

python server.py

Para iniciar el panel de administración:
Bash

python admin.py

🤝 Contribución

Si deseas contribuir a este proyecto, por favor crea un fork del repositorio, crea una nueva rama para tus cambios y envía un Pull Request. Toda mejora a la lógica de validación o a la interfaz gráfica es bienvenida.

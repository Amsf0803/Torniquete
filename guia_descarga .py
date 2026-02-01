"""
Versión mejorada con manejo automático de ChromeDriver
Soluciona problemas de compatibilidad de versiones
"""

import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from pathlib import Path


def setup_driver():
    """Configura Chrome con ChromeDriver automático"""
    options = Options()
    # options.add_argument('--headless')  # Descomenta para ocultar navegador
    options.add_argument('--start-maximized')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    # Intentar encontrar Chrome en ubicaciones comunes de Linux
    chrome_paths = [
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/snap/bin/chromium',
    ]
    
    chrome_found = None
    for path in chrome_paths:
        if os.path.exists(path):
            chrome_found = path
            break
    
    if chrome_found:
        options.binary_location = chrome_found
        print(f"✓ Chrome encontrado en: {chrome_found}")
    
    try:
        # Usar webdriver-manager para manejar versiones automáticamente
        print("Configurando ChromeDriver...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("✓ ChromeDriver configurado correctamente\n")
        return driver
    except Exception as e:
        print(f"Error con webdriver-manager: {e}")
        print("Intentando con ChromeDriver del sistema...\n")
        # Fallback al driver del sistema
        return webdriver.Chrome(options=options)


def login_manual(driver, url, wait_time=30):
    """
    Abre la página y espera login manual
    
    Args:
        driver: Driver de Selenium
        url: URL de la revista
        wait_time: Tiempo de espera para login manual (segundos)
    """
    print(f"Abriendo {url}")
    driver.get(url)
    print(f"\n⚠️  Por favor, haz login manualmente en la ventana del navegador")
    print(f"⏳ Esperando {wait_time} segundos...\n")
    
    for i in range(wait_time, 0, -5):
        print(f"   Tiempo restante: {i} segundos")
        time.sleep(5)
    
    print("\n✓ Continuando con la descarga\n")


def download_image(url, filename):
    """Descarga una imagen desde una URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        return False


def extract_all_images(driver):
    """Extrae todas las URLs de imágenes de la página actual"""
    images = []
    
    # Método 1: Imágenes en tags <img>
    try:
        img_elements = driver.find_elements(By.TAG_NAME, 'img')
        for img in img_elements:
            try:
                src = img.get_attribute('src') or img.get_attribute('data-src')
                if src and (src.startswith('http') or src.startswith('data:')):
                    width = img.size.get('width', 0)
                    height = img.size.get('height', 0)
                    if width > 100 and height > 100:
                        images.append(src)
            except:
                continue
    except Exception as e:
        print(f"  Advertencia: Error extrayendo imgs: {e}")
    
    # Método 2: Imágenes en canvas (común en visualizadores de revistas)
    try:
        canvases = driver.find_elements(By.TAG_NAME, 'canvas')
        for i, canvas in enumerate(canvases):
            try:
                # Convertir canvas a imagen
                data_url = driver.execute_script(
                    "return arguments[0].toDataURL('image/png');", 
                    canvas
                )
                if data_url:
                    images.append(('canvas', i, data_url))
            except:
                continue
    except Exception as e:
        print(f"  Advertencia: Error extrayendo canvas: {e}")
    
    # Método 3: Elementos con background-image
    try:
        bg_images = driver.execute_script("""
            var elements = document.querySelectorAll('*');
            var urls = [];
            for (var i = 0; i < elements.length; i++) {
                var style = window.getComputedStyle(elements[i]);
                var bg = style.backgroundImage;
                if (bg && bg !== 'none') {
                    var match = bg.match(/url\\(["\']?([^"\'\\)]+)["\']?\\)/);
                    if (match && match[1].startsWith('http')) {
                        urls.push(match[1]);
                    }
                }
            }
            return urls;
        """)
        images.extend(bg_images)
    except Exception as e:
        print(f"  Advertencia: Error extrayendo backgrounds: {e}")
    
    return images


def save_canvas_image(data_url, filename):
    """Guarda una imagen de canvas (data URL) a archivo"""
    try:
        import base64
        # Remover el prefijo "data:image/png;base64,"
        image_data = data_url.split(',')[1]
        with open(filename, 'wb') as f:
            f.write(base64.b64decode(image_data))
        return True
    except:
        return False


def simple_download(url, username, password, output_dir="descargas", max_pages=None):
    """
    Función simplificada de descarga
    
    Args:
        url: URL de la revista
        username: Usuario (puede no usarse si login es manual)
        password: Contraseña (puede no usarse si login es manual)
        output_dir: Carpeta de destino
        max_pages: Páginas máximas a descargar (None = ilimitado, para hasta el final)
    """
    # Crear directorio
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Inicializar navegador
    try:
        driver = setup_driver()
    except Exception as e:
        print(f"\n❌ Error al inicializar navegador: {e}")
        print("\nPosibles soluciones:")
        print("1. Instala webdriver-manager: pip install webdriver-manager")
        print("2. Instala Chrome/Chromium: sudo apt install chromium-browser")
        print("3. Actualiza Chrome a la última versión")
        return
    
    downloaded_urls = set()
    consecutive_empty = 0
    
    try:
        # Login manual
        login_manual(driver, url, wait_time=30)
        
        # Descargar cada página
        page_num = 1
        
        while True:
            # Verificar si llegamos al límite (solo si max_pages está definido)
            if max_pages is not None and page_num > max_pages:
                print(f"\n⚠️  Alcanzado límite de {max_pages} páginas")
                break
            
            print(f"\n{'='*50}")
            print(f"📄 PÁGINA {page_num}")
            print(f"{'='*50}")
            
            # Esperar carga completa
            time.sleep(3)
            
            # Scroll para asegurar carga de imágenes lazy
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Obtener todas las imágenes
            print("Extrayendo imágenes...")
            images = extract_all_images(driver)
            new_images = 0
            
            if not images:
                consecutive_empty += 1
                print("⚠️  No se encontraron imágenes en esta página")
                
                if consecutive_empty >= 3:
                    print("\n❌ 3 páginas consecutivas sin imágenes. Finalizando...")
                    break
            else:
                consecutive_empty = 0
                print(f"Encontradas {len(images)} imágenes potenciales")
            
            # Descargar cada imagen
            for i, img_data in enumerate(images):
                try:
                    # Manejar canvas
                    if isinstance(img_data, tuple) and img_data[0] == 'canvas':
                        _, canvas_idx, data_url = img_data
                        filename = f"{output_dir}/page_{page_num:03d}_canvas_{canvas_idx:02d}.png"
                        
                        if save_canvas_image(data_url, filename):
                            print(f"  ✓ Canvas guardado: page_{page_num:03d}_canvas_{canvas_idx:02d}.png")
                            new_images += 1
                        continue
                    
                    # Manejar URLs normales
                    src = img_data
                    
                    # Evitar duplicados
                    if src in downloaded_urls:
                        continue
                    
                    # Generar nombre de archivo
                    ext = '.jpg'
                    if 'png' in src.lower():
                        ext = '.png'
                    elif 'gif' in src.lower():
                        ext = '.gif'
                    elif 'webp' in src.lower():
                        ext = '.webp'
                    
                    filename = f"{output_dir}/page_{page_num:03d}_img_{i:02d}{ext}"
                    
                    # Descargar
                    if download_image(src, filename):
                        print(f"  ✓ Descargada: page_{page_num:03d}_img_{i:02d}{ext}")
                        downloaded_urls.add(src)
                        new_images += 1
                    
                except Exception as e:
                    continue
            
            print(f"\n📊 Resumen: {new_images} imágenes nuevas descargadas")
            
            # Si 3 páginas consecutivas sin imágenes, probablemente llegamos al final
            if consecutive_empty >= 3:
                print(f"\n✓ Detectadas {consecutive_empty} páginas consecutivas sin imágenes")
                print("   Probablemente llegamos al final del documento")
                break
            
            # Intentar avanzar página
            print("\n⏩ Avanzando a siguiente página...")
            
            # Guardar URL actual para detectar si cambió
            url_before = driver.current_url
            
            try:
                # Método 1: Flecha derecha
                body = driver.find_element(By.TAG_NAME, 'body')
                body.send_keys(Keys.ARROW_RIGHT)
                time.sleep(2)
                
                # Verificar si la URL cambió o si seguimos en la misma página
                url_after = driver.current_url
                
                # Si la URL no cambió y no hay imágenes nuevas, probablemente llegamos al final
                if url_before == url_after and new_images == 0:
                    # Intentar una vez más por si acaso
                    body.send_keys(Keys.ARROW_RIGHT)
                    time.sleep(2)
                    
                    # Verificar nuevamente
                    if driver.current_url == url_after:
                        print("\n✓ No se puede avanzar más, llegamos al final del documento")
                        break
                        
            except:
                # Método 2: Buscar botón next
                try:
                    next_button = driver.find_element(By.CSS_SELECTOR, 
                        'button.next, a.next, [class*="next"], [class*="siguiente"]')
                    
                    # Verificar si el botón está deshabilitado (señal de última página)
                    if not next_button.is_enabled() or 'disabled' in next_button.get_attribute('class'):
                        print("\n✓ Botón 'Siguiente' deshabilitado, llegamos al final")
                        break
                    
                    next_button.click()
                    time.sleep(2)
                except:
                    print("\n⚠️  No se pudo avanzar más páginas")
                    print("   Probablemente llegamos al final del documento")
                    break
            
            # Incrementar contador de página
            page_num += 1
        
        print(f"\n{'='*60}")
        print(f"✅ DESCARGA COMPLETA")
        print(f"{'='*60}")
        print(f"📁 Total de imágenes: {len(downloaded_urls) + sum(1 for f in os.listdir(output_dir) if 'canvas' in f)}")
        print(f"📂 Ubicación: {os.path.abspath(output_dir)}")
        print(f"{'='*60}\n")
        
    except KeyboardInterrupt:
        print("\n\n❌ Descarga cancelada por el usuario")
        print(f"📁 Imágenes descargadas hasta ahora: {len(downloaded_urls)}")
    except Exception as e:
        print(f"\n❌ Error durante la descarga: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nCerrando navegador...")
        driver.quit()


# CONFIGURACIÓN RÁPIDA
if __name__ == "__main__":
    
    # ========== CONFIGURA AQUÍ ==========
    URL = "https://app.dems.ipn.mx/MaterialDeApoyoNMS/sistema/Documento.aspx#page/1"
    USERNAME = "utorresbello@gmail.com"  # No se usa con login manual
    PASSWORD = "corolla2009"  # No se usa con login manual
    OUTPUT = "revista_descargas"
    MAX_PAGES = None  # None = descarga hasta el final automáticamente
                      # O especifica un número: MAX_PAGES = 50
    # ====================================
    
    print("\n" + "="*60)
    print("  🚀 DESCARGADOR DE REVISTA WEB")
    print("="*60)
    print(f"\n📌 URL: {URL}")
    print(f"📁 Destino: {OUTPUT}")
    if MAX_PAGES:
        print(f"📄 Páginas máximas: {MAX_PAGES}")
    else:
        print(f"📄 Páginas: Todas (hasta el final)")
    print("\n⚠️  NOTA: Deberás hacer login manualmente cuando se abra el navegador")
    print("="*60 + "\n")
    
    input("⏸️  Presiona ENTER para comenzar...")
    
    simple_download(URL, USERNAME, PASSWORD, OUTPUT, MAX_PAGES)
    
    print("\n✅ Script finalizado. ¡Revisa tu carpeta de descargas!")
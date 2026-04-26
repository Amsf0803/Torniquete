import base64

def descifrar_texto(texto_cifrado):
    clave = "L1A_K3Y"
    try:
        # Decodificamos el base64 a string
        descifrado_b64 = base64.b64decode(texto_cifrado.encode('utf-8')).decode('utf-8')
        
        # Hacemos la operación XOR caracter por caracter usando la clave
        password_final = "".join(chr(ord(c) ^ ord(clave[i % len(clave)])) for i, c in enumerate(descifrado_b64))
        
        return password_final
        
    except Exception as e:
        print(f"Error: {e}")
        return ""

# Lo metemos en un print para ver la magia en la consola
resultado = descifrar_texto("DwB3AAgDNypYcC0mBzp9AS8Af1c0fV8eGwk=")
print(f"Tu contraseña es: {resultado}")
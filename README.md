# proyecto-cursos

## 1. Ejecución inicial
Nos paramos en la carpeta principal del proyecto. Creamos un entorno utilizando Python y entramos en él:
```bash
python3 -m venv venv
source venv/bin/activate
```
Instalamos todos los requerimientos necesarios:
```bash
pip install -r requirements.txt
```
### 2. Ejecución normal
Iniciamos el entorno en dos terminales:
```bash
source venv/bin/activate
```
En la primer terminal iniciamos la aplicación de propuestas:
```bash
cd business-simulator/
streamlit run business_app.py
```
En el segundo terminal iniciamos la página web:
```bash
cd website/
streamlit run company_learning.py
```
## 3. Ruta para registrar una empresa nueva
- En la web solicitar un curso. Completar los datos. Acordarnos CUIL.
- En Flowable rellenar los datos para la propuesta.
- En la aplicación de propuestas aceptamos la propuesta.
- Volvemos a la web e iniciamos sesión con el CUIL de la empresa y de contraseña "empresa123".
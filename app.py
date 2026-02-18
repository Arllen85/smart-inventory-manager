import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import os

# --- CONFIGURACIÓN DE BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect('gestion_negocio_pro.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS productos 
                 (id INTEGER PRIMARY KEY, nombre TEXT, categoria TEXT, stock INTEGER, costo REAL, precio_venta REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventas 
                 (id INTEGER PRIMARY KEY, fecha TEXT, producto_id INTEGER, nombre_prod TEXT, cantidad INTEGER, total REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clientes 
                 (id INTEGER PRIMARY KEY, nombre TEXT, deuda_total REAL, abonos REAL)''')
    conn.commit()
    return conn

conn = init_db()

# --- SISTEMA DE LOGIN ---
def login():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        st.markdown("<h1 style='text-align: center;'>🔐 Acceso al Sistema</h1>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,2,1])
        
        with col2:
            with st.form("login_form"):
                usuario = st.text_input("Usuario")
                clave = st.text_input("Contraseña", type="password")
                boton_login = st.form_submit_button("Entrar")

                if boton_login:
                    if usuario == "Superadmin" and clave == "admin.14$":
                        st.session_state.autenticado = True
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos")
        return False
    return True

# --- INICIO DE LA APLICACIÓN ---
if login():
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

    st.sidebar.title("🏪 Menú Principal")
    menu = ["📊 Dashboard", "📦 Inventario", "🛒 Ventas", "💰 Gastos y Ganancias", "👥 Clientes", "📂 Reportes"]
    choice = st.sidebar.selectbox("Seleccione una opción:", menu)

    # --- LISTA DE CATEGORÍAS ACTUALIZADA ---
    categorias_validas = ["Ropa", "Perfume", "Zapatos", "Cremas", "Otros"]

    if choice == "📊 Dashboard":
        st.title("Panel de Control")
        df_prod = pd.read_sql("SELECT * FROM productos", conn)
        df_ventas = pd.read_sql("SELECT * FROM ventas", conn)
        df_clientes = pd.read_sql("SELECT * FROM clientes", conn)
        
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Ventas Totales", f"${df_ventas['total'].sum():,.2f}")
        with col2:
            deuda_total = (df_clientes['deuda_total'] - df_clientes['abonos']).sum()
            st.metric("Cuentas por Cobrar", f"${deuda_total:,.2f}")
        with col3: st.metric("Productos en Stock", len(df_prod))

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Top Ventas")
            if not df_ventas.empty:
                st.bar_chart(df_ventas.groupby('nombre_prod')['cantidad'].sum())
        with c2:
            st.subheader("Alertas de Inventario")
            stock_bajo = df_prod[df_prod['stock'] <= 5]
            if not stock_bajo.empty:
                st.warning("Stock bajo (menos de 5 unidades):")
                st.dataframe(stock_bajo[['nombre', 'stock']])

    elif choice == "📦 Inventario":
        st.header("📦 Control de Inventario")
        df_p = pd.read_sql("SELECT * FROM productos", conn)
        st.subheader("Existencias Actuales")
        if not df_p.empty:
            st.dataframe(df_p.style.format({"costo": "${:,.2f}", "precio_venta": "${:,.2f}"}), use_container_width=True)
        else: st.info("Inventario vacío.")

        st.divider()
        tab1, tab2 = st.tabs(["➕ Añadir / Editar", "🗑️ Eliminar Producto"])
        with tab1:
            opcion_edicion = st.selectbox("Seleccione (o 'Nuevo')", ["Nuevo"] + df_p['nombre'].tolist())
            d = {"nombre": "", "cat": "Otros", "stock": 0, "costo": 0.0, "precio": 0.0}
            if opcion_edicion != "Nuevo":
                row = df_p[df_p['nombre'] == opcion_edicion].iloc[0]
                d = {"nombre": row['nombre'], "cat": row['categoria'], "stock": row['stock'], "costo": row['costo'], "precio": row['precio_venta']}

            with st.form("form_inv"):
                c1, c2, c3 = st.columns(3)
                nom = c1.text_input("Nombre", value=d["nombre"])
                
                # Cargar índice de la categoría actual para el selector
                default_idx = categorias_validas.index(d["cat"]) if d["cat"] in categorias_validas else 4
                cat = c2.selectbox("Categoría", categorias_validas, index=default_idx)
                
                stk = c3.number_input("Stock", min_value=0, value=int(d["stock"]))
                cos = c1.number_input("Costo", min_value=0.0, value=float(d["costo"]))
                pre = c2.number_input("Precio Venta", min_value=0.0, value=float(d["precio"]))
                if st.form_submit_button("Guardar"):
                    if opcion_edicion == "Nuevo":
                        conn.execute("INSERT INTO productos (nombre, categoria, stock, costo, precio_venta) VALUES (?,?,?,?,?)", (nom, cat, stk, cos, pre))
                    else:
                        conn.execute("UPDATE productos SET nombre=?, categoria=?, stock=?, costo=?, precio_venta=? WHERE nombre=?", (nom, cat, stk, cos, pre, opcion_edicion))
                    conn.commit()
                    st.rerun()

        with tab2:
            if not df_p.empty:
                p_borrar = st.selectbox("Eliminar:", df_p['nombre'].tolist())
                if st.button("❌ Confirmar Borrado"):
                    conn.execute("DELETE FROM productos WHERE nombre = ?", (p_borrar,))
                    conn.commit()
                    st.rerun()

    elif choice == "🛒 Ventas":
        st.header("Registrar Venta")
        df_p = pd.read_sql("SELECT id, nombre, precio_venta, stock FROM productos WHERE stock > 0", conn)
        
        if df_p.empty: 
            st.error("No hay stock disponible.")
        else:
            with st.form("v", clear_on_submit=True):
                p_nom = st.selectbox("Producto", df_p['nombre'].tolist())
                cant = st.number_input("Cantidad", min_value=1, step=1)
                if st.form_submit_button("Vender"):
                    p_data = df_p[df_p['nombre'] == p_nom].iloc[0]
                    if cant <= p_data['stock']:
                        total_venta = p_data['precio_venta'] * cant
                        fecha_v = datetime.now().strftime("%Y-%m-%d %H:%M")
                        conn.execute("INSERT INTO ventas (fecha, producto_id, nombre_prod, cantidad, total) VALUES (?,?,?,?,?)", 
                                     (fecha_v, int(p_data['id']), p_nom, cant, total_venta))
                        conn.execute("UPDATE productos SET stock = stock - ? WHERE id = ?", (cant, int(p_data['id'])))
                        conn.commit()
                        st.success(f"Venta de {p_nom} exitosa")
                        st.rerun()
                    else:
                        st.error(f"Stock insuficiente. Disponible: {p_data['stock']}")

        st.divider()
        st.subheader("📋 Ventas Recientes")
        df_vr = pd.read_sql("SELECT fecha, nombre_prod as Producto, cantidad, total FROM ventas ORDER BY id DESC", conn)
        st.dataframe(df_vr.style.format({"total": "${:,.2f}"}), use_container_width=True)

    elif choice == "💰 Gastos y Ganancias":
        st.header("💰 Finanzas")
        st.subheader("📈 Ganancias por Venta")
        df_v = pd.read_sql("""SELECT v.fecha, v.nombre_prod, v.total, (v.total - (p.costo * v.cantidad)) as ganancia FROM ventas v JOIN productos p ON v.producto_id = p.id""", conn)
        if not df_v.empty:
            st.dataframe(df_v.style.format({"total": "${:,.2f}", "ganancia": "${:,.2f}"}))
        
        st.divider()
        st.subheader("📦 Ganancia Proyectada")
        df_proy = pd.read_sql("SELECT nombre, stock, (precio_venta-costo) as gan_u, ((precio_venta-costo)*stock) as gan_total FROM productos", conn)
        st.dataframe(df_proy.style.format({"gan_u": "${:,.2f}", "gan_total": "${:,.2f}"}))

    elif choice == "👥 Clientes":
        st.header("Control de Clientes")
        with st.form("cli"):
            c1, c2, c3 = st.columns(3)
            nom = c1.text_input("Nombre Cliente")
            deu = c2.number_input("Deuda Nueva", min_value=0.0)
            abo = c3.number_input("Abono", min_value=0.0)
            if st.form_submit_button("Actualizar"):
                check = pd.read_sql(f"SELECT * FROM clientes WHERE nombre = '{nom}'", conn)
                if not check.empty:
                    conn.execute("UPDATE clientes SET deuda_total = deuda_total + ?, abonos = abonos + ? WHERE nombre = ?", (deu, abo, nom))
                else:
                    conn.execute("INSERT INTO clientes (nombre, deuda_total, abonos) VALUES (?,?,?)", (nom, deu, abo))
                conn.commit()
                st.rerun()
        df_c = pd.read_sql("SELECT nombre, deuda_total, abonos, (deuda_total - abonos) as saldo FROM clientes", conn)
        st.dataframe(df_c.style.format({"deuda_total": "${:,.2f}", "abonos": "${:,.2f}", "saldo": "${:,.2f}"}))

    elif choice == "📂 Reportes":
        st.header("Reportes")
        tipo = st.radio("Reporte:", ["Ventas Realizadas", "Inventario y Ganancias", "Estado de Clientes"])
        
        if tipo == "Ventas Realizadas":
            df_exp = pd.read_sql("""SELECT v.fecha, v.nombre_prod as Producto, v.cantidad, v.total, (v.total - (p.costo * v.cantidad)) as Ganancia_Venta
                                    FROM ventas v JOIN productos p ON v.producto_id = p.id""", conn)
        elif tipo == "Inventario y Ganancias":
            df_exp = pd.read_sql("""SELECT p.nombre as Producto, p.categoria as Categoria, p.stock as Stock, p.costo as Costo, p.precio_venta as Precio, (p.precio_venta - p.costo) as Ganancia_U, 
                                    IFNULL(SUM(v.total - (p.costo * v.cantidad)), 0) as Ganancia_Real FROM productos p LEFT JOIN ventas v ON p.id = v.producto_id GROUP BY p.id""", conn)
        else:
            df_exp = pd.read_sql("SELECT nombre as Cliente, deuda_total as Deuda, abonos as Abonos, (deuda_total - abonos) as Saldo_Pendiente FROM clientes", conn)

        st.subheader(f"Vista Previa: {tipo}")
        if not df_exp.empty:
            cols_num = df_exp.select_dtypes(include=['float', 'int']).columns
            st.dataframe(df_exp.style.format({c: "${:,.2f}" for c in cols_num if c not in ['cantidad', 'stock', 'Stock']}), use_container_width=True)

        st.divider()
        ruta = st.text_input("Carpeta para guardar:", "reportes/")
        if st.button("💾 Exportar a Excel"):
            if not df_exp.empty:
                if not os.path.exists(ruta): os.makedirs(ruta)
                path = os.path.join(ruta, f"{tipo.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")
                df_exp.to_excel(path, index=False)
                st.success(f"Guardado en {path}")
                st.download_button("Descargar CSV", df_exp.to_csv().encode('utf-8'), "reporte.csv")

"""
===============================================================================
MÓDULO ETL: EXTRACCIÓN, TRANSFORMACIÓN Y CARGA DE DATOS DE RIESGO
===============================================================================
Descripción:
    Este script ejecuta un proceso ETL automatizado que extrae datos de 
    fuentes públicas (GitHub CSV), normaliza los montos solicitados, evalúa 
    el nivel de riesgo crediticio según reglas de negocio definidas y sincroniza
    los resultados en las tablas relacionales de Supabase (PostgreSQL).
"""

import io
import requests
import pandas as pd
from sqlalchemy import create_engine, text

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE CONEXIÓN Y FUENTE DE DATOS
# -----------------------------------------------------------------------------
# URI de conexión a PostgreSQL en Supabase con driver nativo psycopg2
DB_URI = "postgresql://postgres:Jilary2318.@db.hdavydolxksxctzvkedv.supabase.co:5432/postgres"

# Fuente de datos CSV pública utilizada para simular montos y transacciones
DATA_URL = "https://raw.githubusercontent.com/datasets/gdp/master/data/gdp.csv"


def run_etl():
    """
    Ejecuta el flujo principal del Pipeline ETL:
    1. Extrae información en tiempo real desde la URL configurada.
    2. Transforma los datos numéricos y asigna niveles de riesgo crediticio.
    3. Carga los registros procesados en la base de datos relacional y genera
       un registro de auditoría en la tabla 'etl_fraud_logs'.
    """
    print("=== INICIANDO PROCESO ETL ===")
    
    # -------------------------------------------------------------------------
    # FASE 1: EXTRAER (Extraction)
    # -------------------------------------------------------------------------
    print("1. Descargando archivo desde la URL pública...")
    response = requests.get(DATA_URL)
    
    # Validación del estado de la respuesta HTTP
    if response.status_code != 200:
        print(f"Error en la descarga: Código de estado {response.status_code}")
        return
    
    # Lectura del contenido CSV usando buffer de memoria
    csv_data = io.StringIO(response.text)
    df_raw = pd.read_csv(csv_data)
    print(f"   Descarga exitosa. Registros totales obtenidos: {len(df_raw)}")

    # -------------------------------------------------------------------------
    # FASE 2: TRANSFORMAR (Transformation)
    # -------------------------------------------------------------------------
    print("2. Transformando y evaluando reglas de riesgo...")
    engine = create_engine(DB_URI)
    
    # Selección de un lote inicial de 500 registros para el procesamiento
    df_clean = df_raw.head(500).copy()

    # Conversión segura a formato numérico para evitar errores operacionales
    numeric_values = pd.to_numeric(df_clean['Value'], errors='coerce').fillna(1000000)
    
    # Generación de identificadores fiscales (NIT) y nombres corporativos
    df_clean['tax_id'] = [f"NIT-800{i:03d}-9" for i in range(len(df_clean))]
    df_clean['company_name'] = [f"Empresa Solicitante {i+1} S.A.S." for i in range(len(df_clean))]
    
    # Normalización del monto de crédito solicitado en rango financiero ($5M - $55M COP)
    df_clean['requested_amount'] = (numeric_values % 50000000) + 5000000
    
    def assign_risk(amount):
        """
        Aplica reglas de negocio para clasificar el nivel de riesgo financiero:
        - Riesgo Alto: Monto > $35,000,000
        - Riesgo Medio: Monto entre $15,000,001 y $35,000,000
        - Riesgo Bajo: Monto <= $15,000,000
        """
        if amount > 35000000:
            return 'Alto'
        elif amount > 15000000:
            return 'Medio'
        else:
            return 'Bajo'

    # Aplicación de la función de categorización y banderas de lista negra
    df_clean['risk_level'] = df_clean['requested_amount'].apply(assign_risk)
    df_clean['is_blacklisted'] = df_clean['risk_level'] == 'Alto'

    # -------------------------------------------------------------------------
    # FASE 3: CARGAR (Loading)
    # -------------------------------------------------------------------------
    print("3. Cargando información en Supabase (PostgreSQL)...")
    
    with engine.begin() as conn:
        flagged_count = 0
        
        for _, row in df_clean.iterrows():
            # Inserción / Actualización de entidades corporativas (Upsert)
            conn.execute(
                text("""
                    INSERT INTO corporate_entities (tax_id, company_name, is_blacklisted)
                    VALUES (:tax_id, :company_name, :is_blacklisted)
                    ON CONFLICT (tax_id) DO UPDATE 
                    SET is_blacklisted = EXCLUDED.is_blacklisted;
                """),
                {
                    "tax_id": row['tax_id'],
                    "company_name": row['company_name'],
                    "is_blacklisted": bool(row['is_blacklisted'])
                }
            )
            
            # Registrar la solicitud de crédito en la base de datos
            conn.execute(
                text("""
                    INSERT INTO credit_applications (tax_id, company_name, requested_amount, risk_level)
                    VALUES (:tax_id, :company_name, :requested_amount, :risk_level);
                """),
                {
                    "tax_id": row['tax_id'],
                    "company_name": row['company_name'],
                    "requested_amount": float(row['requested_amount']),
                    "risk_level": row['risk_level']
                }
            )
            
            # Conteo de entidades marcadas con riesgo alto
            if row['is_blacklisted']:
                flagged_count += 1
        
        # Registro final del ciclo ETL en la tabla de auditoría/logs
        conn.execute(
            text("""
                INSERT INTO etl_fraud_logs (records_processed, flagged_entities_count, status)
                VALUES (:records, :flagged, 'SUCCESS');
            """),
            {"records": len(df_clean), "flagged": flagged_count}
        )

    print("=== PROCESO ETL FINALIZADO CON ÉXITO ===")

# Punto de entrada para ejecución por línea de comandos
if __name__ == "__main__":
    run_etl()
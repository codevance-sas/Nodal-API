from sqlmodel import Session, create_engine, SQLModel
from app.models.survey import Survey, Operator, Well
import polars as pl
import gc
import os
from dotenv import load_dotenv

load_dotenv()

supabase_url = f"postgresql+psycopg2://{os.getenv('SUPABASE_USER')}:{os.getenv('SUPABASE_PASSWORD')}@{os.getenv('SUPABASE_HOST')}:{os.getenv('SUPABASE_PORT')}/{os.getenv('SUPABASE_DB')}"

testing = "postgresql+psycopg2://nodal:Nodal2025%40%40@srv691712.hstgr.cloud:5432/nodal"

engine = create_engine(testing, 
                      pool_pre_ping=True,
                      pool_recycle=3600,
                      pool_size=5,
                      max_overflow=10)

print(engine)

def delete_all_tables():
    SQLModel.metadata.drop_all(engine)
    gc.collect()

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    gc.collect()

def populate_table(data_list, batch_size=2000):
    total = len(data_list)

    for i in range(0, total, batch_size):
        end_idx = min(i + batch_size, total)
        batch = data_list[i:end_idx]
        try:
            with Session(engine, autoflush=False) as session:
                session.bulk_save_objects(batch)
                session.commit()
                print(f"Insertados registros {i} a {end_idx} de {total}")
        except Exception as e:
            print(f"Error insertando lote {i} a {end_idx}: {e}")
        finally:
            batch = None
            gc.collect()



def process_csv_in_chunks(csv_path, model_class, batch_size=100, num_batches=5):
    """
    Procesa un CSV en trozos para evitar cargar todo en memoria usando read_csv_batched
    
    Args:
        csv_path: Ruta al archivo CSV
        model_class: Clase del modelo SQLModel
        batch_size: Tamaño del lote para inserción en BD
        num_batches: Número de batches a procesar a la vez
    """
    try:
        # Usar read_csv_batched para inicializar el lector
        # El tamaño del batch aquí afecta cuántos registros se cargan en memoria a la vez
        csv_reader = pl.read_csv_batched(csv_path, batch_size=batch_size)
        
        total_procesados = 0
        
        # Procesar los datos en grupos de num_batches
        while True:
            # next_batches devuelve una lista de DataFrames (o None si no hay más datos)
            batches = csv_reader.next_batches(num_batches)
            if not batches:  # Si no quedan más batches, terminamos
                break
                
            # Recorrer cada batch devuelto
            for chunk_df in batches:
                if chunk_df is None or chunk_df.is_empty():
                    continue
                    
                # Convertir a objetos del modelo según la clase
                if model_class == Operator:
                    objects = [
                        Operator(id=row["id"], operator_name=row["operator_name"])
                        for row in chunk_df.iter_rows(named=True)
                    ]
                elif model_class == Survey:
                    objects = [
                        Survey(id=row["id"], well_id=row["well_id"], survey=row["survey"], 
                               md=row["md"], inc=row["inc"], azm=row["azm"], b=row["b"], 
                               rf=row["rf"], ns=row["ns"], ew=row["ew"], tvd=row["tvd"], 
                               dls=row["dls"], stepout=row["stepout"])
                        for row in chunk_df.iter_rows(named=True)
                    ]
                elif model_class == Well:
                    objects = [
                        Well(
                            id=row["id"],
                            well_name=row["well_name"],
                            operator_id=row["operator_id"],
                            longitude=row["longitude"],
                            latitude=row["latitude"]
                        )
                        for row in chunk_df.iter_rows(named=True)
                    ]
                
                # Insertar los objetos en la base de datos
                num_registros = len(objects)
                populate_table(objects, batch_size)
                
                # Actualizar contador y liberar memoria
                total_procesados += num_registros
                print(f"Procesados {total_procesados} registros en total")
                
                # Liberar memoria
                chunk_df = None
                objects = None
                gc.collect()
        
        print(f"Procesamiento completado. Total de registros: {total_procesados}")
            
    except Exception as e:
        print(f"Error procesando el CSV {csv_path}: {e}")


def main():
    try:
        delete_all_tables()
        create_db_and_tables()
        
        # Procesar operadores
        print("Procesando operadores...")
        process_csv_in_chunks(
            "/home/darkend/Projects/notebooks/operators_df.csv",
            Operator,
            batch_size=10000,
            num_batches=10
        )

        # Procesar pozos
        print("Procesando pozos...")
        process_csv_in_chunks(
            "/home/darkend/Projects/notebooks/wells_df.csv",
            Well,
            batch_size=50000,
            num_batches=10
        )
        # Procesar encuestas
        print("Procesando encuestas...")
        process_csv_in_chunks(
            "/home/darkend/Projects/notebooks/survey_data_df.csv",
            Survey,
            batch_size=1000000,
            num_batches=10
        )
        
        print("Proceso completado con éxito")
    except Exception as e:
        print(f"Error en el proceso principal: {e}")
    finally:
        # Asegurar que la conexión se cierra correctamente
        engine.dispose()
        gc.collect()

if __name__ == "__main__":
    main()


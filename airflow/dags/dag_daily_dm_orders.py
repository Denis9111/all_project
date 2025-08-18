from datetime import datetime
from airflow.models import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator

default_args = {
    "owner": "etl_user",
    "depends_on_past": False,
    "start_date": datetime(2025, 8, 13),
    #"retry_delay": timedelta(minutes=0.1)
}

dag = DAG(
    dag_id='dag_daily_dm_orders',
    default_args=default_args,
    schedule_interval='1 * * * *',
    catchup=True,
    max_active_tasks=3,
    max_active_runs=1,
    tags=["data marts", "dm_orders"]
)

clear_day = PostgresOperator(
    task_id='clear_day',
    postgres_conn_id='main_postgresql_connection',
    sql="""DELETE FROM public.dm_orders WHERE "buy_date"::date = '{{ ds }}'::date""",
    dag=dag)


calc_day = PostgresOperator(
    task_id='calc_day',
    postgres_conn_id='main_postgresql_connection',
    sql="""insert into dm_orders(buy_date, product_name, order_city_name, customer_name, account_number, customer_city_name, total_value, total_costs)
select buy_time::timestamp as buy_date, 
P.product_name as product_name, 
C.city_name as order_city_name, 
CU.customer_name as customer_name, 
CU.account_number as account_number,
CC.city_name as customer_city_name,
SUM(value) as total_value, 
SUM(costs) as total_costs
FROM f_orders O
LEFT JOIN d_cities C on
	O.city_id = C.id
LEFT JOIN d_products as P on
	O.product_id = P.id
LEFT JOIN d_customers CU on 
	O.customer_id = CU.id
LEFT JOIN d_cities as CC on
	CU.city_id = CC.id
--WHERE buy_time::date = '{{ ds }}'::date
group by buy_date, product_name, order_city_name, customer_name, account_number, customer_city_name;""",
    dag=dag)

clear_day >> calc_day
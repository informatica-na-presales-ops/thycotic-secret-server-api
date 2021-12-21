import apscheduler.schedulers.blocking
import notch
import os
import psycopg2.extras
import secret_server
import signal
import sys

log = notch.make_log('sync-ops-web-passwords')


def get_db_connection():
    cnx = psycopg2.connect(os.getenv('DB'), cursor_factory=psycopg2.extras.DictCursor)
    return cnx


def get_ops_web_data(cnx) -> list[dict]:
    with cnx:
        with cnx.cursor() as cur:
            sql = 'select cloud, machine_id, password from windows_credentials'
            cur.execute(sql)
            data = cur.fetchall()
    return data


def update_ops_web_row(cnx, machine_id):
    with cnx:
        with cnx.cursor() as cur:
            sql = '''update windows_credentials set password = '_exported_' where machine_id = %(machine_id)s'''
            cur.execute(sql, {'machine_id': machine_id})


def get_secrets_list(ssc):
    params = {
        'filter.folderId': (os.getenv('SECRET_SERVER_FOLDER_ID')),
        'take': 100,
    }
    return list(ssc.get_secrets(params))


def main_job():
    cnx = get_db_connection()
    ssc = secret_server.SecretServerClient()
    ops_web_rows = get_ops_web_data(cnx)
    all_secrets = get_secrets_list(ssc)
    thycotic_secret_names = [row.get('name') for row in all_secrets]
    for ops_web_row in ops_web_rows:
        cloud = ops_web_row.get('cloud')
        machine_id = ops_web_row.get('machine_id')
        candidate_secret_name = f'{cloud}.{machine_id}'
        if candidate_secret_name in thycotic_secret_names:
            if ops_web_row.get('password') == '_exported_':
                log.info(f'{candidate_secret_name} is already saved in Secret Server')
            else:
                log.info(f'{candidate_secret_name} has an updated password')
                secret_id = None
                for secret in all_secrets:
                    if secret.get('name') == candidate_secret_name:
                        secret_id = secret.get('id')
                        break
                ssc.delete_secret(secret_id)
                ssc.post_secrets(int(os.getenv('SECRET_SERVER_FOLDER_ID')), candidate_secret_name, 'Administrator',
                                 ops_web_row.get('password'))
        else:
            log.info(f'{candidate_secret_name} needs to be added to Secret Server')
            ssc.post_secrets(int(os.getenv('SECRET_SERVER_FOLDER_ID')), candidate_secret_name, 'Administrator',
                             ops_web_row.get('password'))
            update_ops_web_row(cnx, ops_web_row.get('machine_id'))


def main():
    repeat = os.getenv('REPEAT', 'false').lower() in ('1', 'on', 'true', 'yes')
    if repeat:
        repeat_interval_minutes = int(os.getenv('REPEAT_INTERVAL_MINUTES', 15))
        log.info(f'This job will repeat every {repeat_interval_minutes} minutes')
        log.info('Change this value by setting the REPEAT_INTERVAL_MINUTES environment variable')
        scheduler = apscheduler.schedulers.blocking.BlockingScheduler()
        scheduler.add_job(main_job, 'interval', minutes=repeat_interval_minutes)
        scheduler.add_job(main_job)
        scheduler.start()
    else:
        main_job()


def handle_sigterm(_signal, _frame):
    sys.exit()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, handle_sigterm)
    main()

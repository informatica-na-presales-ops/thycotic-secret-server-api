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
            sql = '''select cloud, machine_id, password from windows_credentials where password <> '_exported_' '''
            cur.execute(sql)
            data = cur.fetchall()
    return data


def update_ops_web_row(cnx, machine_id):
    with cnx:
        with cnx.cursor() as cur:
            sql = '''update windows_credentials set password = '_exported_' where machine_id = %(machine_id)s'''
            cur.execute(sql, {'machine_id': machine_id})


def get_secrets_list(ssc) -> dict:
    params = {
        'filter.folderId': (os.getenv('SECRET_SERVER_FOLDER_ID')),
        'take': 100,
    }
    return {s.get('name'): s.get('id') for s in ssc.get_secrets(params)}


def main_job():
    cnx = get_db_connection()
    ops_web_rows = get_ops_web_data(cnx)
    if len(ops_web_rows) < 1:
        log.info(f'No new passwords in Ops Web')
        return
    elif len(ops_web_rows) > 1:
        log.info(f'{len(ops_web_rows)} new passwords in Ops Web')
    else:
        log.info('1 new password in Ops Web')

    ssc = secret_server.SecretServerClient()
    all_secrets = get_secrets_list(ssc)
    for ops_web_row in ops_web_rows:
        cloud = ops_web_row.get('cloud')
        machine_id = ops_web_row.get('machine_id')
        candidate_secret_name = f'{cloud}.{machine_id}'
        if candidate_secret_name in all_secrets:
            log.info(f'{candidate_secret_name} has an updated password')
            secret_id = all_secrets.get(candidate_secret_name)
            ssc.delete_secret(secret_id)
        else:
            log.info(f'{candidate_secret_name} needs to be added to Secret Server')
        folder_id = int(os.getenv('SECRET_SERVER_FOLDER_ID'))
        ssc.post_secrets(folder_id, candidate_secret_name, 'Administrator', ops_web_row.get('password'))
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

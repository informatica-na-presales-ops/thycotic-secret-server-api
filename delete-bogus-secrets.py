import notch
import os
import psycopg2.extras
import secret_server

log = notch.make_log('delete-bogus-secrets')


def get_db_connection():
    cnx = psycopg2.connect(os.getenv('DB'), cursor_factory=psycopg2.extras.DictCursor)
    return cnx


def get_ops_web_data(cnx) -> list[dict]:
    with cnx:
        with cnx.cursor() as cur:
            sql = '''
                select concat('aws.', v.id) secret_name
                from virtual_machines v
                join windows_credentials c on c.machine_id = v.id
                where v.visible is true and v.platform = 'linux'
            '''
            cur.execute(sql)
            data = cur.fetchall()
    return data


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
        log.info('No bogus passwords')
        return
    elif len(ops_web_rows) > 1:
        log.info(f'{len(ops_web_rows)} bogus passwords to remove from Thycotic')
    else:
        log.info('1 bogus password to remove from Thycotic')

    ssc = secret_server.SecretServerClient()
    all_secrets = get_secrets_list(ssc)
    for ops_web_row in ops_web_rows:
        secret_name = ops_web_row.get('secret_name')
        if secret_name in all_secrets:
            log.info(f'{secret_name} needs to be removed')
            secret_id = all_secrets.get(secret_name)
            ssc.delete_secret(secret_id)
        else:
            log.info(f'{secret_name} was not found in Thycotic')


if __name__ == '__main__':
    main_job()

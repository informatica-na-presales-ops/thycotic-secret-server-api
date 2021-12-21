import apscheduler.schedulers.blocking
import notch
import os
import psycopg2.extras
import signal
import sys

log = notch.make_log('sync-ops-web-passwords')


def get_ops_web_data():
    cnx = psycopg2.connect(os.getenv('DB'), cursor_factory=psycopg2.extras.DictCursor)
    with cnx:
        with cnx.cursor() as cur:
            sql = 'select cloud, machine_id, password from windows_credentials'
            cur.execute(sql)
            data = cur.fetchall()
    cnx.close()
    return data


def main_job():
    for row in get_ops_web_data():
        log.info(f'ops-web data row: {row}')


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

from apscheduler.schedulers.background import BackgroundScheduler

from .routes.internal import run_poll_gazette, run_send_digests


def configure_scheduler(app) -> None:
    if not app.config.get("ENABLE_DEV_SCHEDULER", False):
        return

    scheduler = BackgroundScheduler(timezone="Africa/Nairobi")

    def poll_wrapper() -> None:
        with app.app_context():
            run_poll_gazette()

    def digest_wrapper() -> None:
        with app.app_context():
            run_send_digests()

    scheduler.add_job(poll_wrapper, "cron", minute="0", hour="*/4", id="poll_gazette", replace_existing=True)
    scheduler.add_job(digest_wrapper, "cron", day_of_week="mon", hour=9, minute=0, id="send_digests", replace_existing=True)
    scheduler.start()


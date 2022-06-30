import logging
import datetime


class DeltaTimeFormatter(logging.Formatter):
    def format(self, record):
        duration = datetime.datetime.utcfromtimestamp(record.relativeCreated / 1000)
        record.delta = duration.strftime("%H:%M:%S")
        return super().format(record)


# ROOT LOG CONFIG
LOG_LEVEL = 'INFO'
logging.getLogger().setLevel(LOG_LEVEL)
handler = logging.StreamHandler()
LOGFORMAT = '+%(delta)s %(funcName)-9s() %(levelname)-9s: %(message)s'
fmt = DeltaTimeFormatter(LOGFORMAT)
handler.setFormatter(fmt)
logging.getLogger().addHandler(handler)

# MODULE LOG CONFIG
log = logging.getLogger(__name__)
log.setLevel(LOG_LEVEL)

# need these down here to respect my logging config

from scene_generator.main import main

if __name__ == '__main__':
    main()

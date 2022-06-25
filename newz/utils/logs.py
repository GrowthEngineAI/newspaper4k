import sys
import json
import logging
from pathlib import Path
from loguru import logger
from typing import Optional

LoggerConfigs = {
    "default": {
        "level": "info",
        "format": "<level>{level: <8}</level> <green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> - <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
    },
    "fastapi": {
        "path:": "/var/logs",
        "filename": "app.log",
        "level": "info",
        "rotation": "20 days",
        "retention": "1 months",
        "format": "<level>{level: <8}</level> <green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> request id: {extra[request_id]} - <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
    }
}

LoggerFormats = {
    'default': "<level>{level: <8}</level> <green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> - <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    'fastapi': "<level>{level: <8}</level> <green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> request id: {extra[request_id]} - <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
}

class InterceptHandler(logging.Handler):
    loglevel_mapping = {
        50: 'CRITICAL',
        40: 'ERROR',
        30: 'WARNING',
        20: 'INFO',
        10: 'DEBUG',
        5: 'CRITICAL',
        4: 'ERROR',
        3: 'WARNING',
        2: 'INFO',
        1: 'DEBUG',
        0: 'NOTSET',
    }
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        #except AttributeError:
        except ValueError:
            level = self.loglevel_mapping[record.levelno]
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        log = logger.bind(request_id='app')
        log.opt(
            depth=depth,
            exception=record.exc_info
        ).log(level,record.getMessage())


class CustomizeLogger:

    @classmethod
    def make_logger(cls, config_path: Optional[Path] = None):
        config = cls.load_logging_config(config_path) if config_path else LoggerConfigs
        logging_config = config.get('logger', config.get('default'))
        return cls.customize_logging(
            logging_config.get('path') ,
            level = logging_config.get('level'),
            retention = logging_config.get('retention'),
            rotation = logging_config.get('rotation'),
            format = logging_config.get('format')
        )

    @classmethod
    def make_default_logger(cls, module_name: str, level: str = 'info', **kwargs):
        """
        We'll adjust this later to use a ConfigModel
        """
        logger.remove()
        logger.add(
            sys.stdout,
            enqueue = True,
            backtrace = True,
            colorize = True,
            level = level.upper(),
            format = LoggerFormats['default'],
            #filter = module_name,
        )
        # logger.add(
        #     sys.stderr,
        #     enqueue = True,
        #     backtrace = True,
        #     level = level.upper(),
        #     format = LoggerFormats['default'],
        #     #filter = module_name,
        # )

        logging.basicConfig(handlers=[InterceptHandler()], level=0)
        logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]
        for _log in ['uvicorn',
                     'uvicorn.error',
                     'fastapi'
                     ]:
            _logger = logging.getLogger(_log)
            _logger.handlers = [InterceptHandler()]
        return logger.bind(request_id=None, method=None)


    @classmethod
    def customize_logging(cls, filepath: Path, level: str, rotation: str, retention: str, format: str):
        logger.remove()
        #fsock = open('/var/logs/logs.txt', 'w')
        #sys.stdout = sys.stderr = fsock
        logger.add(
            sys.stdout,
            enqueue=True,
            backtrace=True,
            level=level.upper(),
            format=format
        )
        logger.add(
            str(filepath),
            rotation=rotation,
            retention=retention,
            enqueue=True,
            backtrace=True,
            level=level.upper(),
            format=format
        )
        logging.basicConfig(handlers=[InterceptHandler()], level=0)
        logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]
        for _log in ['uvicorn',
                     'uvicorn.error',
                     'fastapi'
                     ]:
            _logger = logging.getLogger(_log)
            _logger.handlers = [InterceptHandler()]
        return logger.bind(request_id=None, method=None)


    @classmethod
    def load_logging_config(cls, config_path):
        config = None
        with open(config_path) as config_file:
            config = json.load(config_file)
        return config

get_logger = CustomizeLogger.make_default_logger
default_logger = CustomizeLogger.make_default_logger('kops')
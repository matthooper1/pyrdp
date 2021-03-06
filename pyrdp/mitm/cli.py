#
# This file is part of the PyRDP project.
# Copyright (C) 2020 GoSecure Inc.
# Licensed under the GPLv3 or later.
#

"""
File that contains methods related to the MITM command line.
To be consumed either via bin/pyrdp-mitm.py or via twistd plugin.
"""
import argparse
import logging
import logging.handlers
import os
import sys
from typing import Tuple
from pathlib import Path
from base64 import b64encode

import OpenSSL

from pyrdp.core.ssl import ServerTLSContext
from pyrdp.core import settings
from pyrdp.logging import LOGGER_NAMES, configure as configureLoggers
from pyrdp.mitm.config import MITMConfig, DEFAULTS


def parseTarget(target: str) -> Tuple[str, int]:
    """
    Parse a target host:port and return components. Port is optional.
    """
    if ":" in target:
        targetHost = target[: target.index(":")]
        targetPort = int(target[target.index(":") + 1:])
    else:
        targetHost = target
        targetPort = 3389
    return targetHost, targetPort


def validateKeyAndCertificate(private_key: str, certificate: str) -> Tuple[str, str]:
    if (private_key is None) != (certificate is None):
        sys.stderr.write("You must provide both the private key and the certificate")
        sys.exit(1)
    elif private_key is None:
        key, cert = getSSLPaths()
        handleKeyAndCertificate(key, cert)
    else:
        key, cert = private_key, certificate

    try:
        # Check if OpenSSL accepts the private key and certificate.
        ServerTLSContext(key, cert)
    except OpenSSL.SSL.Error as error:
        from pyrdp.logging import log
        log.error(
            "An error occurred when creating the server TLS context. " +
            "There may be a problem with your private key or certificate (e.g: signature algorithm too weak). " +
            "Here is the exception: %(error)s",
            {"error": error}
        )
        sys.exit(1)

    return key, cert


def handleKeyAndCertificate(key: str, certificate: str):
    """
    Handle the certificate and key arguments that were given on the command line.
    :param key: path to the TLS private key.
    :param certificate: path to the TLS certificate.
    """

    from pyrdp.logging import LOGGER_NAMES
    logger = logging.getLogger(LOGGER_NAMES.MITM)

    if os.path.exists(key) and os.path.exists(certificate):
        logger.info("Using existing private key: %(privateKey)s", {"privateKey": key})
        logger.info("Using existing certificate: %(certificate)s", {"certificate": certificate})
    else:
        logger.info("Generating a private key and certificate for SSL connections")

        if generateCertificate(key, certificate):
            logger.info("Private key path: %(privateKeyPath)s", {"privateKeyPath": key})
            logger.info("Certificate path: %(certificatePath)s", {"certificatePath": certificate})
        else:
            logger.error("Generation failed. Please provide the private key and certificate with -k and -c")


def getSSLPaths() -> (str, str):
    """
    Get the path to the TLS key and certificate in pyrdp's config directory.
    :return: the path to the key and the path to the certificate.
    """

    if not os.path.exists(settings.CONFIG_DIR):
        os.makedirs(settings.CONFIG_DIR)

    key = settings.CONFIG_DIR + "/private_key.pem"
    certificate = settings.CONFIG_DIR + "/certificate.pem"
    return key, certificate


def generateCertificate(keyPath: str, certificatePath: str) -> bool:
    """
    Generate an RSA private key and certificate with default values.
    :param keyPath: path where the private key should be saved.
    :param certificatePath: path where the certificate should be saved.
    :return: True if generation was successful
    """

    if os.name != "nt":
        nullDevicePath = "/dev/null"
    else:
        nullDevicePath = "NUL"

    result = os.system("openssl req -newkey rsa:2048 -nodes -keyout %s -x509 -days 365 -out %s -subj \"/CN=www.example.com/O=PYRDP/C=US\" 2>%s" % (keyPath, certificatePath, nullDevicePath))
    return result == 0


def showConfiguration(config: MITMConfig):
    logging.getLogger(LOGGER_NAMES.MITM).info("Target: %(target)s:%(port)d", {"target": config.targetHost, "port": config.targetPort})
    logging.getLogger(LOGGER_NAMES.MITM).info("Output directory: %(outputDirectory)s", {"outputDirectory": config.outDir.absolute()})


def buildArgParser():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="IP:port of the target RDP machine (ex: 192.168.1.10:3390)")
    parser.add_argument("-l", "--listen", help="Port number to listen on (default: 3389)", default=3389)
    parser.add_argument("-o", "--output", help="Output folder", default="pyrdp_output")
    parser.add_argument("-i", "--destination-ip", help="Destination IP address of the PyRDP player.If not specified, RDP events are not sent over the network.")
    parser.add_argument("-d", "--destination-port", help="Listening port of the PyRDP player (default: 3000).", default=3000)
    parser.add_argument("-k", "--private-key", help="Path to private key (for SSL)")
    parser.add_argument("-c", "--certificate", help="Path to certificate (for SSL)")
    parser.add_argument("-u", "--username", help="Username that will replace the client's username", default=None)
    parser.add_argument("-p", "--password", help="Password that will replace the client's password", default=None)
    parser.add_argument("-L", "--log-level", help="Console logging level. Logs saved to file are always verbose.", default="INFO", choices=["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("-F", "--log-filter", help="Only show logs from this logger name (accepts '*' wildcards)", default="")
    parser.add_argument("-s", "--sensor-id", help="Sensor ID (to differentiate multiple instances of the MITM where logs are aggregated at one place)", default="PyRDP")
    parser.add_argument("--payload", help="Command to run automatically upon connection", default=None)
    parser.add_argument("--payload-powershell", help="PowerShell command to run automatically upon connection", default=None)
    parser.add_argument("--payload-powershell-file", help="PowerShell script to run automatically upon connection (as -EncodedCommand)", default=None)
    parser.add_argument("--payload-delay", help="Time to wait after a new connection before sending the payload, in milliseconds", default=None)
    parser.add_argument("--payload-duration", help="Amount of time for which input / output should be dropped, in milliseconds. This can be used to hide the payload screen.", default=None)
    parser.add_argument("--disable-active-clipboard", help="Disables the active clipboard stealing to request clipboard content upon connection.", action="store_true")
    parser.add_argument("--crawl", help="Enable automatic shared drive scraping", action="store_true")
    parser.add_argument("--crawler-match-file", help="File to be used by the crawler to chose what to download when scraping the client shared drives.", default=None)
    parser.add_argument("--crawler-ignore-file", help="File to be used by the crawler to chose what folders to avoid when scraping the client shared drives.", default=None)
    parser.add_argument("--no-replay", help="Disable replay recording", action="store_true")
    parser.add_argument("--no-downgrade", help="Disables downgrading of unsupported extensions. This makes PyRDP harder to fingerprint but might impact the player's ability to replay captured traffic.", action="store_true")
    parser.add_argument("--no-files", help="Do not extract files transferred between the client and server.", action="store_true")
    parser.add_argument("--transparent", help="Spoof source IP for connections to the server (See README)", action="store_true")

    return parser


def configure(cmdline=None) -> MITMConfig:
    parser = buildArgParser()

    if cmdline:
        args = parser.parse_args(cmdline)
    else:
        args = parser.parse_args()

    # Load configuration file.
    cfg = settings.load(settings.CONFIG_DIR + '/mitm.ini', DEFAULTS)

    # Override some of the switches based on command line arguments.
    if args.output:
        cfg.set('vars', 'output_dir', args.output)
    if args.log_filter:
        cfg.set('logs', 'filter', args.log_filter)
    if args.log_level:
        cfg.set('vars', 'level', args.log_level)

    configureLoggers(cfg)
    logger = logging.getLogger(LOGGER_NAMES.PYRDP)

    outDir = Path(cfg.get('vars', 'output_dir'))
    outDir.mkdir(exist_ok=True)

    targetHost, targetPort = parseTarget(args.target)
    key, certificate = validateKeyAndCertificate(args.private_key, args.certificate)

    config = MITMConfig()
    config.targetHost = targetHost
    config.targetPort = targetPort
    config.privateKeyFileName = key
    config.listenPort = int(args.listen)
    config.certificateFileName = certificate
    config.attackerHost = args.destination_ip
    config.attackerPort = int(args.destination_port)
    config.replacementUsername = args.username
    config.replacementPassword = args.password
    config.outDir = outDir
    config.enableCrawler = args.crawl
    config.crawlerMatchFileName = args.crawler_match_file
    config.crawlerIgnoreFileName = args.crawler_ignore_file
    config.recordReplays = not args.no_replay
    config.downgrade = not args.no_downgrade
    config.transparent = args.transparent
    config.extractFiles = not args.no_files
    config.disableActiveClipboardStealing = args.disable_active_clipboard

    payload = None
    powershell = None

    if int(args.payload is not None) + int(args.payload_powershell is not None) + int(args.payload_powershell_file is not None) > 1:
        logger.error("Only one of --payload, --payload-powershell and --payload-powershell-file may be supplied.")
        sys.exit(1)

    if args.payload is not None:
        payload = args.payload
        logger.info("Using payload: %(payload)s", {"payload": args.payload})
    elif args.payload_powershell is not None:
        powershell = args.payload_powershell
        logger.info("Using powershell payload: %(payload)s", {"payload": args.payload_powershell})
    elif args.payload_powershell_file is not None:
        if not os.path.exists(args.payload_powershell_file):
            logger.error("Powershell file %(path)s does not exist.", {"path": args.payload_powershell_file})
            sys.exit(1)

        try:
            with open(args.payload_powershell_file, "r") as f:
                powershell = f.read()
        except IOError as e:
            logger.error("Error when trying to read powershell file: %(error)s", {"error": e})
            sys.exit(1)

        logger.info("Using payload from powershell file: %(path)s", {"path": args.payload_powershell_file})

    if powershell is not None:
        payload = "powershell -EncodedCommand " + b64encode(powershell.encode("utf-16le")).decode()

    if payload is not None:
        if args.payload_delay is None:
            logger.error("--payload-delay must be provided if a payload is provided.")
            sys.exit(1)

        if args.payload_duration is None:
            logger.error("--payload-duration must be provided if a payload is provided.")
            sys.exit(1)

        try:
            config.payloadDelay = int(args.payload_delay)
        except ValueError:
            logger.error("Invalid payload delay. Payload delay must be an integral number of milliseconds.")
            sys.exit(1)

        if config.payloadDelay < 0:
            logger.error("Payload delay must not be negative.")
            sys.exit(1)

        if config.payloadDelay < 1000:
            logger.warning("You have provided a payload delay of less than 1 second. We recommend you use a slightly longer delay to make sure it runs properly.")

        try:
            config.payloadDuration = int(args.payload_duration)
        except ValueError:
            logger.error("Invalid payload duration. Payload duration must be an integral number of milliseconds.")
            sys.exit(1)

        if config.payloadDuration < 0:
            logger.error("Payload duration must not be negative.")
            sys.exit(1)

        config.payload = payload
    elif args.payload_delay is not None:
        logger.error("--payload-delay was provided but no payload was set.")
        sys.exit(1)

    showConfiguration(config)
    return config

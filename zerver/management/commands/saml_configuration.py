import datetime
import io
import logging
import os
from argparse import ArgumentParser
from typing import Any, Dict, Iterator, List, Tuple

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import make_aware as timezone_make_aware
from django.utils.timezone import now as timezone_now
from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser as Parser
from onelogin.saml2.utils import OneLogin_Saml2_Utils as Utils

# The template for the path to the IdP certificate.
IDP_CERT_PATH_TEMPLATE: str = "/etc/zulip/saml/idps/{}.crt"
# The format string used for logging.
LOG_FORMAT: str = "%(levelname)s:%(asctime)s {}: %(message)s".format(__file__)


def is_valid(cert: x509.Certificate) -> bool:
    """Check if the given certificate is currently valid."""
    now: datetime.datetime = timezone_now()
    return now >= timezone_make_aware(cert.not_valid_before) and now <= timezone_make_aware(
        cert.not_valid_after
    )


def public_cert_open(cert_path: str, fix_permissions: bool = True) -> io.TextIOWrapper:
    """Open/create a file for a public certificate.

    If the file needs to be created, its permissions are set to
    `-rw-r--r--` (0644). If the file already exists, the permissions
    will only be changed if 'fix_permissions' is true (the default).
    If the current umask value is more restrictive, it dominates the
    new permissions.

    Return an open file object. May raise an OSError, for example, if
    the file already exists and is a directory.
    """
    flags: int = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    mode: int = 0o644

    if os.path.isfile(cert_path) and os.stat(cert_path).st_mode != mode:
        if fix_permissions:
            os.chmod(cert_path, mode)
        else:
            logging.warning("file '%s' does not have mode %o", mode)

    # At this point, the mode of the file will stay unchanged if it
    # already exists.
    return os.fdopen(os.open(cert_path, flags, mode), mode="w")


class Command(BaseCommand):
    help = """

Manage some of the SAML configuration automatically.

Current status:
Keep the signing certificates of the IdPs listed in
settings.SOCIAL_AUTH_SAML_ENABLED_IDPS up to date. This works by
connecting to the server where the IdP's metadata is stored and
downloading the IdP's certificates.

For this to work, you need to configure the "metadata_url" field in
the IdP sections of settings.SOCIAL_AUTH_SAML_ENABLED_IDPS and set it
to the url of the IdP's metadata XML file. Please also make sure that
you provide a https link (so that SSL can be used for communication)
and that you can trust the server from which we get the metadata XML
file. Otherwise, your authentication system may be compromised.
"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--fix-permissions",
            action="store_true",
            help="additionally fix inappropriate certificate file permissions",
        )
        parser.add_argument(
            "metadata_url",
            nargs="?",
            type=str,
            help="manually provide a metadata url for testing; no file changes will be made; the received certificate will be printed to stdout; requires [entity_id]",
        )
        parser.add_argument(
            "entity_id",
            nargs="?",
            type=str,
            help="manually provide an entity_id for testing; requires [metadata_url]",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        def do_handle_idp(
            idp: str, entity_id: str, metadata_url: str, test_mode: bool = False
        ) -> None:
            # The list of the IdPs signing certificates.
            certs_list: List[str] = []
            new_cert: str
            new_cert_object: x509.Certificate

            # Get the data from the metadata url of the IdP.
            data: Dict[str, Any] = Parser.parse_remote(
                metadata_url, validate_cert=True, entity_id=entity_id
            )

            if "idp" not in data:
                logging.error("Cannot receive metadata for IdP %s", idp)
                logging.debug(data)
                return

            # Some documentation:
            # - https://github.com/onelogin/python3-saml
            # - https://github.com/onelogin/python3-saml/blob/master/src\
            #     /onelogin/saml2/idp_metadata_parser.py

            if "x509cert" in data["idp"]:
                # A single certificate, used for both signing and encryption.
                certs_list.append(data["idp"]["x509cert"])
            elif "x509certMulti" in data["idp"] and "signing" in data["idp"]["x509certMulti"]:
                # There are multiple certificates, maybe different ones for
                # signing and encryption.
                certs_list.extend(data["idp"]["x509certMulti"]["signing"])

            if not certs_list:
                logging.error("Cannot find any certificates for IdP %s", idp)
                return

            # Format the certificates properly.
            # See https://github.com/onelogin/python3-saml/blob/master/src\
            #   /onelogin/saml2/utils.py
            certs: Iterator[str] = map(Utils.format_cert, certs_list)

            # Map the certificates to their x509 objects in order to be able to
            # determine the validity of the certificate.
            # See https://cryptography.io/en/latest/x509/reference.html\
            #   #cryptography.x509.Certificate
            certs_objects: Iterator[Tuple[str, x509.Certificate]] = (
                (cert, x509.load_pem_x509_certificate(cert.encode(), backend=default_backend()))
                for cert in certs
            )

            # Check for the best certificate available:
            #  - It is currently valid.
            #  - It is valid for as long as possible.
            try:
                new_cert, new_cert_object = max(
                    (
                        (cert, cert_object)
                        for cert, cert_object in certs_objects
                        if is_valid(cert_object)
                    ),
                    key=lambda t: t[1].not_valid_after,
                )
            except ValueError:
                logging.error("Cannot find any valid certificate for IdP %s", idp)
                logging.debug("", exc_info=True)
                return

            cert_path: str = IDP_CERT_PATH_TEMPLATE.format(idp)

            if test_mode:
                print(f"Woule write to '{cert_path}':\n", new_cert)
            else:
                # Write the certificate to the appropriate location.
                try:
                    with public_cert_open(
                        cert_path, fix_permissions=options["fix_permissions"]
                    ) as f:
                        f.write(new_cert)
                except OSError:
                    logging.error("Cannot write certificate for IdP %s", idp)
                    return

        logging.basicConfig(format=LOG_FORMAT)

        if options["entity_id"] is not None and options["metadata_url"] is not None:
            do_handle_idp("test_idp", options["entity_id"], options["metadata_url"], test_mode=True)
            return
        if options["entity_id"] is not None or options["metadata_url"] is not None:
            raise CommandError(
                "Argument error: if entity_id or metadata_url is given, both need to be present"
            )

        # The dictionary storing the enabled IdPs (using their names as keys).
        idps: Dict[str, Any] = settings.SOCIAL_AUTH_SAML_ENABLED_IDPS

        for idp in idps:
            # Check the provided settings.
            if "metadata_url" not in idps[idp] or "entity_id" not in idps[idp]:
                logging.error(
                    "No 'metadata_url' and/or 'entity_id' field for IdP '%s' in the SAML configuration",
                    idp,
                )
                continue

            # Check whether this setting has been configured.
            if not idps[idp]["metadata_url"]:
                logging.warning("'metadata_url' not configured for IdP '%s'", idp)
                continue

            do_handle_idp(idp, idps[idp]["entity_id"], idps[idp]["metadata_url"])

"""
Cliente boto3 para o Cloudflare R2.

Uso:
    from app.utils.r2 import get_r2, R2_BUCKET

    s3 = get_r2()
    s3.upload_fileobj(f, R2_BUCKET, "cnpj/2025/01/arquivo.txt")
"""

import os
import urllib3
import boto3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

R2_BUCKET = os.getenv("R2_BUCKET", "sped-manager")


def get_r2():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("R2_SECRET_KEY"),
        region_name="auto",
        verify=False,
    )


def upload_bytes(key: str, conteudo: bytes) -> None:
    get_r2().put_object(Bucket=R2_BUCKET, Key=key, Body=conteudo)


def download_bytes(key: str) -> bytes:
    obj = get_r2().get_object(Bucket=R2_BUCKET, Key=key)
    return obj["Body"].read()


def r2_key_efd(cnpj: str, nome_padronizado: str) -> str:
    """Gera o path no R2 para um arquivo EFD. Ex: efd/10607929000137/10607929000137_20250101_20250131.txt"""
    return f"efd/{cnpj}/{nome_padronizado}"


def r2_key_xml(cnpj: str, chv_nfe: str) -> str:
    """Gera o path no R2 para um XML NFC-e/NF-e. Ex: xml/10607929000137/31250110607929...xml"""
    return f"xml/{cnpj}/{chv_nfe}.xml"

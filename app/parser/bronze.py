from datetime import datetime
from sqlalchemy.orm import Session
from app.models.efd_raw import EfdRaw


class BronzeProcessor:
    def __init__(self, session: Session, tenant_id: int):
        self.session = session
        self.tenant_id = tenant_id

    def arquivo_ja_ingerido(self, nome_padronizado: str) -> bool:
        existe = (
            self.session.query(EfdRaw)
            .filter(
                EfdRaw.tenant_id == self.tenant_id,
                EfdRaw.file_path == nome_padronizado
            )
            .first()
        )
        return existe is not None

    def ingerir(self, conteudo: str, nome_padronizado: str) -> dict:
        if self.arquivo_ja_ingerido(nome_padronizado):
            return {
                "status": "ignorado",
                "motivo": "arquivo já ingerido anteriormente",
                "linhas": 0
            }

        ingest_timestamp = datetime.utcnow()
        linhas = conteudo.splitlines()
        objetos = []

        for i, linha in enumerate(linhas):
            linha = linha.strip()
            if not linha:
                continue

            campos = linha.split('|')
            tipo = campos[1] if len(campos) > 1 else 'DESCONHECIDO'

            objetos.append(EfdRaw(
                tenant_id=self.tenant_id,
                file_path=nome_padronizado,
                num_linha=i + 1,
                tipo_registro=tipo,
                conteudo_linha=linha,
                ingest_timestamp=ingest_timestamp
            ))

        tamanho_lote = 1000
        for i in range(0, len(objetos), tamanho_lote):
            self.session.bulk_save_objects(objetos[i:i + tamanho_lote])
            self.session.commit()

        return {
            "status": "concluido",
            "linhas": len(objetos),
            "arquivo": nome_padronizado
        }
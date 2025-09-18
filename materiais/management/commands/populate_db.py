import random
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from materiais.models import (
    SolicitacaoCompra, ItemSolicitacao, User, Obra, ItemCatalogo,
    Fornecedor, Cotacao, ItemCotacao, RequisicaoMaterial, Recebimento
)

class Command(BaseCommand):
    help = 'Limpa e popula o banco de dados com 15 SCs de teste com ciclo de vida completo.'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("--- INICIANDO SCRIPT COMPLETO DE POPULAÇÃO ---"))

        # 1. APAGAR DADOS ANTIGOS
        self.stdout.write("Apagando Solicitações de Compra, Cotações, RMs e Recebimentos antigos...")
        Recebimento.objects.all().delete()
        RequisicaoMaterial.objects.all().delete()
        Cotacao.objects.all().delete()
        SolicitacaoCompra.objects.all().delete()
        self.stdout.write(self.style.SUCCESS("Dados antigos apagados com sucesso."))

        # 2. VERIFICAR DADOS ESSENCIAIS
        self.stdout.write(self.style.NOTICE("\nVerificando dados essenciais (usuários, obras, itens, fornecedores)..."))
        try:
            solicitantes = list(User.objects.filter(perfil__in=['almoxarife_obra', 'engenheiro']))
            aprovadores = list(User.objects.filter(perfil__in=['engenheiro', 'diretor']))
            compradores = list(User.objects.filter(perfil='almoxarife_escritorio'))
            recebedores = list(User.objects.filter(perfil='almoxarife_obra'))
            obras = list(Obra.objects.filter(ativa=True))
            itens_catalogo = list(ItemCatalogo.objects.filter(ativo=True))
            fornecedores = list(Fornecedor.objects.filter(ativo=True))

            if not all([solicitantes, obras, itens_catalogo, fornecedores, aprovadores, compradores, recebedores]):
                raise Exception("Dados insuficientes para popular o banco de dados.")
            self.stdout.write(self.style.SUCCESS("Dados essenciais encontrados."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"\nERRO: {e}"))
            self.stderr.write(self.style.ERROR("Por favor, certifique-se de que existem usuários, obras, itens e fornecedores cadastrados."))
            return

        # 3. DEFINIR STATUS FINAIS
        status_finais = [
            'pendente_aprovacao', 'aprovada', 'aprovada',
            'em_cotacao', 'em_cotacao',
            'finalizada', 'finalizada', 'finalizada',
            'a_caminho', 'a_caminho', 'a_caminho',
            'recebida', 'recebida',
            'rejeitada', 'pendente_aprovacao'
        ]
        random.shuffle(status_finais)

        # 4. CRIAR 15 SOLICITAÇÕES COMPLETAS
        self.stdout.write(self.style.NOTICE("\nCriando 15 novas Solicitações de Compra com ciclo de vida completo..."))
        for i in range(15):
            status_final = status_finais[i]
            obra_selecionada = random.choice(obras)
            
            sc = SolicitacaoCompra.objects.create(
                solicitante=random.choice(solicitantes),
                obra=obra_selecionada,
                data_necessidade=timezone.now().date() + timedelta(days=random.randint(10, 40)),
                justificativa=f"SC de teste {i+1} para a obra '{obra_selecionada.nome}'.",
                status='pendente_aprovacao'
            )

            num_itens = random.randint(3, 6)
            itens_para_sc = random.sample(itens_catalogo, min(num_itens, len(itens_catalogo)))
            for item_cat in itens_para_sc:
                ItemSolicitacao.objects.create(
                    solicitacao=sc, item_catalogo=item_cat, descricao=item_cat.descricao,
                    unidade=item_cat.unidade.sigla, categoria=str(item_cat.categoria),
                    quantidade=random.randint(5, 200)
                )
            
            self.stdout.write(f"  - SC ({sc.numero}) criada...")

            if status_final != 'pendente_aprovacao':
                sc.status = 'aprovada'
                sc.aprovador = random.choice(aprovadores)
                sc.data_aprovacao = sc.data_criacao + timedelta(days=random.randint(1, 3))
                sc.save()

            if status_final == 'rejeitada':
                sc.status = 'rejeitada'
                sc.save()

            if status_final in ['finalizada', 'a_caminho', 'recebida']:
                sc.status = 'finalizada'
                
                cotacao_vencedora = Cotacao.objects.create(
                    solicitacao=sc, fornecedor=random.choice(fornecedores),
                    # --- CORREÇÃO APLICADA AQUI ---
                    valor_frete=Decimal(str(round(random.uniform(50.0, 150.0), 2))),
                    vencedora=True,
                    data_cotacao = sc.data_aprovacao + timedelta(days=random.randint(1, 4))
                )
                subtotal_itens = Decimal('0.0')
                for item_solicitado in sc.itens.all():
                    preco_float = round(random.uniform(10.0, 300.0), 2)
                    preco_decimal = Decimal(str(preco_float))
                    ItemCotacao.objects.create(cotacao=cotacao_vencedora, item_solicitacao=item_solicitado, preco=preco_decimal)
                    subtotal_itens += preco_decimal * item_solicitado.quantidade
                
                rm = RequisicaoMaterial.objects.create(
                    solicitacao_origem=sc, cotacao_vencedora=cotacao_vencedora,
                    valor_total=subtotal_itens + cotacao_vencedora.valor_frete, status_assinatura='assinada'
                )
                sc.save()
                self.stdout.write(self.style.SUCCESS(f"    -> Cotação vencedora e RM ({rm.numero}) geradas."))

                if status_final in ['a_caminho', 'recebida']:
                    sc.status = 'a_caminho'
                    sc.save()
                
                if status_final == 'recebida':
                    Recebimento.objects.create(
                        solicitacao=sc, recebedor=random.choice(recebedores),
                        data_recebimento=cotacao_vencedora.data_cotacao + timedelta(days=random.randint(2, 5))
                    )
                    sc.status = 'recebida'
                    sc.save()
                    self.stdout.write(self.style.SUCCESS("    -> Itens marcados como recebidos."))

        self.stdout.write(self.style.SUCCESS("\n--- SCRIPT CONCLUÍDO ---"))
        self.stdout.write(self.style.SUCCESS("Dados populados com sucesso! Verifique seu dashboard de relatórios."))
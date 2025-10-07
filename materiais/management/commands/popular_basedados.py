from django.core.management.base import BaseCommand
from materiais.models import UnidadeMedida, CategoriaItem

class Command(BaseCommand):
    help = 'Popula ou atualiza o banco de dados com as Categorias e Unidades de Medida padrão.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Iniciando a atualização da base de dados...'))

        # 1. Popula Unidades de Medida (sem alterações)
        self.stdout.write('Verificando Unidades de Medida...')
        unidades = [
            # --- Unidades existentes ---
            {'nome': 'Unidade', 'sigla': 'UN'},
            {'nome': 'Metro', 'sigla': 'M'},
            {'nome': 'Metro Quadrado', 'sigla': 'M²'},
            {'nome': 'Metro Cúbico', 'sigla': 'M³'},
            {'nome': 'Vara', 'sigla': 'VARA'},
            {'nome': 'Dúzia', 'sigla': 'DZ'},
            {'nome': 'Saco', 'sigla': 'SC'},
            {'nome': 'Tonelada', 'sigla': 'TON'},
            {'nome': 'Pacote', 'sigla': 'PCT'},
            {'nome': 'Litro', 'sigla': 'L'},
            {'nome': 'Quilograma', 'sigla': 'KG'},
            {'nome': 'Lata', 'sigla': 'LATA'},
            {'nome': 'Caixa', 'sigla': 'CX'},
            {'nome': 'Rolo', 'sigla': 'ROLO'},
            {'nome': 'Peça', 'sigla': 'PÇ'},

            # --- Novas Sugestões ---
            {'nome': 'Vergalhão', 'sigla': 'VG'},      # Para barras de aço de diferentes diâmetros.
            {'nome': 'Folha', 'sigla': 'FL'},          # Para chapas de compensado, gesso (drywall), etc.
            {'nome': 'Par', 'sigla': 'PAR'},          # Para itens vendidos em pares (ex: luvas, botas).
            {'nome': 'Jogo', 'sigla': 'JG'},           # Para conjuntos de ferramentas ou kits.
            {'nome': 'Balde', 'sigla': 'BD'},          # Para tintas, massas e argamassas.
            {'nome': 'Cento', 'sigla': 'CENTO'},      # Para tijolos, blocos (compra por centenas).
            {'nome': 'Milheiro', 'sigla': 'MIL'},      # Para grandes quantidades de tijolos ou blocos.
            {'nome': 'Barra', 'sigla': 'BAR'},
            {'nome': 'Conexão', 'sigla': 'CON'},
            {'nome': 'Galão', 'sigla': 'GL'}

          # Para diárias de serviços ou aluguel de equipamentos.

        ]
        for unidade in unidades:
            obj, created = UnidadeMedida.objects.get_or_create(sigla=unidade['sigla'], defaults={'nome': unidade['nome']})
            if created:
                self.stdout.write(f'  - Unidade "{obj.nome}" criada.')
        self.stdout.write(self.style.SUCCESS('Unidades de Medida verificadas com sucesso!'))

        # 2. Popula Categorias e Subcategorias com a ESTRUTURA FINAL E CORRIGIDA
        self.stdout.write('\nVerificando Categorias e Subcategorias...')
        estrutura_categorias = {
            'Instalações': ['Elétrico', 'Hidrossanitário', 'Incêndio', 'Gás', 'SPDA', 'Telefônica', 'Lógica', 'Internet'],
            'Estrutura': ['Ferro', 'Alvenaria', 'Carpintaria', 'Agregados', 'Pré-moldados'],
            'Esquadrias': ['Madeira', 'Aço', 'Ferragem'],
            'Acabamentos': ['Revestimento', 'Louças', 'Piso', 'Granitos', 'Acessórios Metálicos', 'Pintura', 'Forro'],
            'Gerais': ['Aditivo', 'Medicamentos', 'Limpeza', 'Utensílio', 'Material para escritório'],
            'Piscina': ['Acessórios de piscina'],
            'Agregados': ['Areia', 'Seixo'],
            'Paisagismo': ['Plantas', 'Mudas de mini ixora', 'Mudas de pingo de ouro', 'Grama em placas'],
            'Equipamentos': ['Ferramentas'],
            'Fardamento': ['Calça', 'Camisa administração', 'Camisa reciclando', 'Camisa mestre de obras', 'Camisa geral'],
            'Refrigeração': ['Equipamentos de Refrigeração'],
            'Segurança do Trabalho': ['EPI', 'Tela Tapume'],
            'Serviços': ['Serviços de Manutenção'],
        }

        for cat_nome, sub_nomes in estrutura_categorias.items():
            cat_obj, created = CategoriaItem.objects.get_or_create(nome=cat_nome, categoria_mae=None)
            if created:
                self.stdout.write(f'  - Categoria principal "{cat_obj.nome}" criada.')
            
            for sub_nome in sub_nomes:
                sub_obj, sub_created = CategoriaItem.objects.get_or_create(nome=sub_nome, categoria_mae=cat_obj)
                if sub_created:
                    self.stdout.write(f'    - Subcategoria "{sub_obj.nome}" criada em "{cat_obj.nome}".')
        
        self.stdout.write(self.style.SUCCESS('Categorias e Subcategorias verificadas com sucesso!'))
        self.stdout.write(self.style.SUCCESS('\nAtualização da base de dados concluída!'))
# Arquivo de Configuração para a Requisição de Material (RM)
# Modifique os dados aqui para que eles reflitam em todos os PDFs gerados.

DADOS_EMPRESA_A = {
    'KEY': 'A',
    'NOME': 'Construtora Boa Vista Ltda',
    'ENDERECO': 'Taumaturgo de Azevedo,-Centro, 64001-340, Teresina - PI',
    'CNPJ': '07.215.619/0001-62',
    'TELEFONE': '(86) 3221-8064',
    'EMAIL': 'boavista@construtoraboavista.com.br',
    'CIDADE_PADRAO': 'Teresina', # Cidade que aparecerá no campo de data da assinatura
    'CNPJ_COMPLETO': 'CNPJ nº 07215619000162 - Insc. Est.', # Campo para exibição completa
    'LOGO_URL': '/static/logo/boavista_logo.png', # Caminho do logo na pasta static
}

DADOS_EMPRESA_B = {
    'KEY': 'B',
    'NOME': 'FR. Incorporações e Construções LTDA.',
    'ENDERECO': 'Taumaturgo de Azevedo,-Centro, 64001-340, Teresina - PI',
    'CNPJ': '12.162.486/0001-43',
    'TELEFONE': '(86) 3221-8064',
    'EMAIL': 'boavista@construtoraboavista.com.br',
    'CIDADE_PADRAO': 'Teresina',
    'CNPJ_COMPLETO': 'CNPJ nº 12162486000143 - Insc. Est.',
    'LOGO_URL': '/static/logo/boavista_logo.png',
}


# Dicionário de dicionários para armazenar todas as opções
DADOS_EMPRESAS = {
    'A': DADOS_EMPRESA_A,
    'B': DADOS_EMPRESA_B,
}

# Lista de CHOICES para o Django (usada no models.py e views.py)
HEADER_CHOICES = [
    ('A', f"RM - {DADOS_EMPRESA_A['NOME']}"),
    ('B', f"RM - {DADOS_EMPRESA_B['NOME']}"),
]

# Variável padrão mantida para compatibilidade (mas será sobrescrita pela view)
DADOS_EMPRESA = DADOS_EMPRESA_A
# Crie o arquivo: materiais/management/commands/generate_embeddings.py

import google.generativeai as genai
from django.core.management.base import BaseCommand
from materiais.models import CategoriaItem
from django.conf import settings
import time

class Command(BaseCommand):
    help = 'Gera e salva os embeddings vetoriais para as categorias de itens, usado pela busca semântica.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("--- Iniciando Geração de Embeddings ---"))
        
        try:
            api_key = settings.GEMINI_API_KEY
            if not api_key:
                self.stdout.write(self.style.ERROR("ERRO: GEMINI_API_KEY não encontrada nas configurações do Django."))
                return
            genai.configure(api_key=api_key)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro ao configurar a API do Gemini: {e}"))
            return

        self.stdout.write("Buscando categorias para processar...")
        
        # Vamos processar todas as categorias, incluindo as principais
        categorias = list(CategoriaItem.objects.all())
        model = 'models/embedding-001' # Modelo específico para gerar embeddings
        
        updated_count = 0
        total_count = len(categorias)
        
        for i, categoria in enumerate(categorias):
            # O texto usado para gerar o embedding é o caminho completo (Pai > Filho)
            text_to_embed = str(categoria)
            
            self.stdout.write(f"({i+1}/{total_count}) Gerando para: '{text_to_embed}'...")
            
            try:
                result = genai.embed_content(model=model, content=text_to_embed)
                
                # A API retorna uma lista de números (o vetor)
                categoria.embedding = result['embedding']
                categoria.save(update_fields=['embedding'])
                updated_count += 1
                time.sleep(1) # Adiciona uma pausa para não sobrecarregar a API
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  -> Erro ao gerar embedding para '{text_to_embed}': {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nConcluído! {updated_count} de {total_count} embeddings foram gerados/atualizados com sucesso."))
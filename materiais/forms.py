from django import forms
from .models import SolicitacaoCompra, ItemSolicitacao, Obra, ItemCatalogo, Fornecedor

class FornecedorForm(forms.ModelForm):
    class Meta:
        model = Fornecedor
        fields = '__all__' # Ou liste os campos que você quer no formulário
        widgets = { # Adicione classes do Bootstrap para estilização
            'nome_fantasia': forms.TextInput(attrs={'class': 'form-control'}),
            'razao_social': forms.TextInput(attrs={'class': 'form-control'}),
            # ... outros campos
        }

class SolicitacaoCompraForm(forms.ModelForm):
    class Meta:
        model = SolicitacaoCompra
        fields = ['obra', 'data_necessidade', 'justificativa']
        widgets = {
            'obra': forms.Select(attrs={'class': 'form-control'}),
            'data_necessidade': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'justificativa': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        labels = {
            'obra': 'Obra',
            'data_necessidade': 'Data de Necessidade',
            'justificativa': 'Justificativa',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar apenas obras ativas
        self.fields['obra'].queryset = Obra.objects.filter(ativa=True)

class ItemSolicitacaoForm(forms.ModelForm):
    class Meta:
        model = ItemSolicitacao
        fields = ['descricao', 'quantidade', 'unidade', 'observacoes']
        widgets = {
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'unidade': forms.TextInput(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'descricao': 'Descrição do Item',
            'quantidade': 'Quantidade',
            'unidade': 'Unidade',
            'observacoes': 'Observações',
        }
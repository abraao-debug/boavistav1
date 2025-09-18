document.addEventListener('DOMContentLoaded', function () {
    // --- SELETORES DOS ELEMENTOS PRINCIPAIS ---
    const scSelect = $('#sc-select');
    const form = document.getElementById('form-recebimento');
    const dynamicContent = document.getElementById('dynamic-content');
    const detalhesContent = document.getElementById('detalhes-sc-content');
    const itensList = document.getElementById('lista-itens-receber');
    const btnConfirmar = document.getElementById('btn-confirmar');
    
    scSelect.select2({ placeholder: "Selecione uma SC para recebimento" });

    // --- CARREGA DADOS DA SC QUANDO SELECIONADA ---
    scSelect.on('change', function() {
        const solicitacaoId = this.value;
        if (!solicitacaoId) {
            dynamicContent.classList.add('d-none');
            return;
        }
        
        detalhesContent.innerHTML = '<p class="text-center">Carregando detalhes...</p>';
        itensList.innerHTML = '<p class="text-center">Carregando itens...</p>';
        dynamicContent.classList.remove('d-none');
        updateSubmitButtonState(); // Reseta o botão ao carregar nova SC

        fetch(`/api/itens-para-receber/${solicitacaoId}/`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Preenche detalhes da SC
                    detalhesContent.innerHTML = `
                        <div class="row">
                            <div class="col-md-3"><strong>Número:</strong> ${data.sc.numero}</div>
                            <div class="col-md-3"><strong>Solicitante:</strong> ${data.sc.solicitante}</div>
                            <div class="col-md-3"><strong>Obra:</strong> ${data.sc.obra}</div>
                            <div class="col-md-3"><strong>Data:</strong> ${data.sc.data_criacao}</div>
                        </div>`;

                    // Preenche lista de itens
                    let itemsHtml = '';
                    if (data.itens.length > 0) {
                        data.itens.forEach(item => {
                            itemsHtml += `
                            <div class="card mb-2 item-row">
                                <div class="card-body">
                                    <div class="row align-items-center">
                                        <div class="col-1"><input class="form-check-input item-checkbox" type="checkbox" name="itens_selecionados" value="${item.id}"></div>
                                        <div class="col-4"><strong>${item.descricao}</strong></div>
                                        <div class="col-2"><small class="text-muted">Pendente: ${item.quantidade_pendente}</small></div>
                                        <div class="col-2">
                                            <input type="number" name="quantidade_recebida_${item.id}" class="form-control form-control-sm item-quantidade" placeholder="Qtd." step="0.01" max="${item.quantidade_pendente}" min="0" disabled>
                                        </div>
                                        <div class="col-3"><input type="text" name="observacoes_${item.id}" class="form-control form-control-sm" placeholder="Obs. item"></div>
                                    </div>
                                </div>
                            </div>`;
                        });
                    } else {
                        itemsHtml = '<p class="text-center text-success"><strong><i class="fas fa-check-circle"></i> Todos os itens desta SC já foram recebidos.</strong></p>';
                    }
                    itensList.innerHTML = itemsHtml;
                } else {
                    detalhesContent.innerHTML = '<p class="text-center text-danger">Erro ao carregar detalhes.</p>';
                    itensList.innerHTML = '<p class="text-center text-danger">Erro ao carregar itens.</p>';
                }
            });
    });

    // --- LÓGICA DE VALIDAÇÃO E INTERATIVIDADE ---

    function updateSubmitButtonState() {
        const count = document.querySelectorAll('.item-checkbox:checked').length;
        btnConfirmar.textContent = `Confirmar Recebimento (${count} item${count !== 1 ? 's' : ''})`;
        btnConfirmar.disabled = count === 0;
    }

    itensList.addEventListener('change', function(e) {
        if (e.target.classList.contains('item-checkbox')) {
            const itemRow = e.target.closest('.item-row');
            const quantidadeInput = itemRow.querySelector('.item-quantidade');

            if (e.target.checked) {
                quantidadeInput.disabled = false;
                quantidadeInput.required = true;
            } else {
                quantidadeInput.disabled = true;
                quantidadeInput.required = false;
                quantidadeInput.value = '';
                quantidadeInput.classList.remove('is-invalid');
            }
            updateSubmitButtonState();
        }
    });

    form.addEventListener('submit', function(event) {
        event.preventDefault();
        
        let errors = [];
        document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));

        const itensChecados = document.querySelectorAll('.item-checkbox:checked');
        if (itensChecados.length === 0) {
            errors.push('Selecione pelo menos um item para registrar o recebimento.');
        } else {
            itensChecados.forEach(checkbox => {
                const itemRow = checkbox.closest('.item-row');
                const quantidadeInput = itemRow.querySelector('.item-quantidade');
                const descricao = itemRow.querySelector('strong').textContent;
                
                if (!quantidadeInput.value || parseFloat(quantidadeInput.value) <= 0) {
                    errors.push(`- Informe uma quantidade válida para o item: "${descricao}".`);
                    quantidadeInput.classList.add('is-invalid');
                }
            });
        }

        const fileInputs = form.querySelectorAll('input[type="file"][required]');
        fileInputs.forEach(input => {
            if (input.files.length === 0) {
                const label = input.closest('.col-md-4').querySelector('label').textContent;
                errors.push(`- O anexo "${label}" é obrigatório.`);
                input.closest('.upload-box').classList.add('is-invalid');
            }
        });

        if (errors.length > 0) {
            alert('Por favor, corrija os seguintes erros:\n\n' + errors.join('\n'));
        } else {
            form.submit();
        }
    });
    
    document.getElementById('btn-selecionar-todos').addEventListener('click', () => {
        document.querySelectorAll('.item-checkbox').forEach(cb => {
            if (!cb.checked) {
                cb.checked = true;
                cb.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    });

    document.getElementById('btn-desmarcar-todos').addEventListener('click', () => {
        document.querySelectorAll('.item-checkbox').forEach(cb => {
            if (cb.checked) {
                cb.checked = false;
                cb.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    });
});

function updateFileName(input) {
    const uploadBox = input.parentElement;
    uploadBox.classList.remove('is-invalid');
    const fileNameSpan = uploadBox.querySelector('.file-name');
    const uploadTextSpan = uploadBox.querySelector('.upload-text');
    if (input.files.length > 0) {
        fileNameSpan.textContent = input.files[0].name;
        uploadTextSpan.textContent = 'Alterar arquivo';
    } else {
        fileNameSpan.textContent = '';
        uploadTextSpan.textContent = 'Clique para anexar';
    }
}
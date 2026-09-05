(function() {
    function initCustomSelects() {
        document.querySelectorAll('select[data-custom-select]').forEach(select => {
            if (select.dataset.customSelectInitialized) return;
            select.dataset.customSelectInitialized = true;
            
            select.style.display = 'none';
            
            const wrapper = document.createElement('div');
            wrapper.className = 'custom-select-wrapper';
            
            const trigger = document.createElement('div');
            trigger.className = 'custom-select-trigger';
            
            const menu = document.createElement('div');
            menu.className = 'custom-select-menu';
            
            wrapper.appendChild(trigger);
            wrapper.appendChild(menu);
            select.parentNode.insertBefore(wrapper, select.nextSibling);
            
            function updateMenu() {
                menu.innerHTML = '';
                let selectedText = '';
                Array.from(select.options).forEach(opt => {
                    if (opt.selected && !opt.disabled && opt.value) {
                        selectedText = opt.textContent;
                    }
                    const item = document.createElement('div');
                    item.className = 'custom-select-item';
                    if (opt.disabled) item.classList.add('disabled');
                    if (opt.selected) item.classList.add('selected');
                    item.textContent = opt.textContent;
                    item.dataset.value = opt.value;
                    
                    if (!opt.disabled) {
                        item.addEventListener('click', (e) => {
                            e.stopPropagation();
                            select.value = opt.value;
                            trigger.textContent = opt.textContent;
                            select.dispatchEvent(new Event('change'));
                            wrapper.classList.remove('open');
                            
                            // Cập nhật lại UI selected
                            Array.from(menu.children).forEach(c => c.classList.remove('selected'));
                            item.classList.add('selected');
                        });
                    }
                    menu.appendChild(item);
                });
                
                if (!selectedText) {
                    const firstValid = Array.from(select.options).find(o => !o.disabled && o.value);
                    trigger.textContent = firstValid ? firstValid.textContent : 'Chọn...';
                } else {
                    trigger.textContent = selectedText;
                }
            }
            
            updateMenu();
            
            const observer = new MutationObserver(updateMenu);
            observer.observe(select, { childList: true });
            
            trigger.addEventListener('click', (e) => {
                e.stopPropagation();
                const isOpen = wrapper.classList.contains('open');
                document.querySelectorAll('.custom-select-wrapper').forEach(w => w.classList.remove('open'));
                if (!isOpen) wrapper.classList.add('open');
            });
            
            menu.addEventListener('click', (e) => {
                e.stopPropagation();
            });
            
            document.addEventListener('click', () => {
                wrapper.classList.remove('open');
            });
            
            select.addEventListener('change', () => {
                 updateMenu();
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCustomSelects);
    } else {
        initCustomSelects();
    }
    
    // Xuất hàm khởi tạo ra toàn cục để gọi lại nếu DOM thay đổi
    window.initCustomSelects = initCustomSelects;
})();

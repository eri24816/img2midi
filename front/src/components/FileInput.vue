
<template>
    <button @click="handleFileUpload">
        <slot></slot>
    </button>
</template>

<script setup lang="ts">
const emit = defineEmits<{
    (e: 'selected', file: File): void
}>();

const handleFileUpload = () => {
    const input = document.createElement("input");
    input.type="file";
    input.click();
    input.onchange = function(){
        emit('selected', input.files?.[0]);
    };
};
</script>
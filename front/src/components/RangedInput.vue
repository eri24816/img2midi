<!-- a slider restricted to a range and step. -->
<template>
    <div class="ranged-input">
        <input type="range" :min="min" :max="max" :step="step" v-model="value1" @input="updateValue" @change="handleChange" />
        <input type="number" :min="min" :max="max" :step="step" v-model="value1" @input="updateValue" @change="handleChange" />
    </div>
</template>

<script setup lang="ts">    
import { ref, onMounted } from 'vue';

const props = defineProps<{
    min: number;
    max: number;
    step: number;
}>();

const value1 = ref(0);

const value = defineModel<number>({required: true});

onMounted(() => {
    value1.value = value.value;
});

const updateValue = (event: Event) => {
    const target = event.target as HTMLInputElement;
    value.value = Math.min(Math.max(Math.floor(parseFloat(target.value) / props.step) * props.step, props.min), props.max);
}

const handleChange = (event: Event) => {
    const target = event.target as HTMLInputElement;
    value.value = Math.min(Math.max(Math.floor(parseFloat(target.value) / props.step) * props.step, props.min), props.max);
    value1.value = value.value;
}
</script>
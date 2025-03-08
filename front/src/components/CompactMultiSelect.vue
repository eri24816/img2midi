<!-- a compact multi select component looks like [1][2][3][4][5][6][7][8][9][10], multiple squares right next to each other -->
<template>
    <div class="compact-multi-select">
        <div 
            v-for="item in items" 
            :key="item" 
            class="compact-multi-select-item"
            :class="{ selected: modelValue.includes(item) }"
            @click="toggleItem(item)"
        >
            {{ item }}
        </div>
    </div>
</template>

<script setup lang="ts">
import { watch } from 'vue';

const props = defineProps<{
    items: number[];
    modelValue: number[];
    minSize?: number;
    maxSize?: number;
}>();

const emit = defineEmits<{
    (e: 'update:modelValue', value: number[]): void;
}>();

// if items change, remove the modelValue if it is not in the new items
watch(() => props.items, (newItems) => {
    const filteredValue = props.modelValue.filter((item) => newItems.includes(item));
    emit('update:modelValue', filteredValue);
});

const toggleItem = (item: number) => {
    const newValue = [...props.modelValue];
    const index = newValue.indexOf(item);
    
    if (index === -1) {
        // Check if adding would exceed maxSize
        if (props.maxSize !== undefined && newValue.length >= props.maxSize) {
            return; // Don't add if it would exceed maxSize
        }
        newValue.push(item);
        // sort the array with the order of the original array
        newValue.sort((a, b) => props.items.indexOf(a) - props.items.indexOf(b));
    } else {
        // Check if removing would go below minSize
        if (props.minSize !== undefined && newValue.length <= props.minSize) {
            return; // Don't remove if it would go below minSize
        }
        newValue.splice(index, 1);
    }
    
    emit('update:modelValue', newValue);
};
</script>

<style scoped>
.compact-multi-select {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 0px;
}

.compact-multi-select-item {
    border: 1px solid #4e4e5a;
    padding: 4px 8px;
    width: 30px;
    height: 30px;
    cursor: pointer;
    user-select: none;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
}

.compact-multi-select-item.selected {
    background-color: #324438;
    color: rgb(150, 255, 150);
    border: 1px solid rgb(103, 197, 103);
    box-shadow: 0 0 5px 0 rgba(154, 255, 154, 0.5);
}

.compact-multi-select-item:hover {
    filter: brightness(1.2);
}

.compact-multi-select-item.selected:hover {

    box-shadow: 0 0 13px 0 rgba(154, 255, 154, 0.5);
}

</style>
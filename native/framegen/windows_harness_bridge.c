/* Synthetic-test loader chain only; never included in the game runtime.
 * Author: djultra64. SPDX-License-Identifier: MIT
 * Wine supplies its Vulkan driver thunk rather than the Windows desktop loader.
 * This bridges a native PE layer into that thunk to exercise Windows code/GPU
 * behavior. It does not test Windows loader discovery or native Windows WSI.
 */
#include "windows_compat.h"
#define AFMF_TEST_BRIDGE_IMPLEMENTATION
#include "windows_harness_bridge.h"
#include <vulkan/vk_layer.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define AFMF_TEST_FUNCTION(name) PFN_##name win_##name;
#include "windows_harness_functions.inc"
#undef AFMF_TEST_FUNCTION

static PFN_vkGetInstanceProcAddr host_gipa, layer_gipa;
static PFN_vkGetDeviceProcAddr host_gdpa, layer_gdpa;
static VkInstance instance;
static PFN_vkVoidFunction load_command(HMODULE module, const char *name)
{
    FARPROC address = GetProcAddress(module, name);
    PFN_vkVoidFunction result;
    _Static_assert(sizeof result == sizeof address, "Windows function pointer width");
    memcpy(&result, &address, sizeof result);
    return result;
}

static VKAPI_ATTR VkResult VKAPI_CALL lower_create_instance(
    const VkInstanceCreateInfo *info, const VkAllocationCallbacks *alloc, VkInstance *output)
{
    VkInstanceCreateInfo lower = *info;
    const VkBaseInStructure *next = lower.pNext;
    while (next && next->sType == VK_STRUCTURE_TYPE_LOADER_INSTANCE_CREATE_INFO) next = next->pNext;
    lower.pNext = next;
    lower.enabledLayerCount = 0;
    lower.ppEnabledLayerNames = NULL;
    return ((PFN_vkCreateInstance)host_gipa(NULL, "vkCreateInstance"))(&lower, alloc, output);
}
static VKAPI_ATTR VkResult VKAPI_CALL lower_create_device(
    VkPhysicalDevice physical, const VkDeviceCreateInfo *info,
    const VkAllocationCallbacks *alloc, VkDevice *output)
{
    VkDeviceCreateInfo lower = *info;
    const VkBaseInStructure *next = lower.pNext;
    while (next && next->sType == VK_STRUCTURE_TYPE_LOADER_DEVICE_CREATE_INFO) next = next->pNext;
    lower.pNext = next;
    lower.enabledLayerCount = 0;
    lower.ppEnabledLayerNames = NULL;
    return ((PFN_vkCreateDevice)host_gipa(instance, "vkCreateDevice"))(physical, &lower, alloc, output);
}
static VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL lower_gipa(VkInstance handle, const char *name)
{
    if (!strcmp(name, "vkCreateInstance")) return (PFN_vkVoidFunction)lower_create_instance;
    if (!strcmp(name, "vkCreateDevice")) return (PFN_vkVoidFunction)lower_create_device;
    return host_gipa(handle, name);
}
static VKAPI_ATTR VkResult VKAPI_CALL device_loader_data(VkDevice device, void *object)
{
    /* Wine has already initialized the handle's dispatch metadata. */
    (void)device; (void)object;
    return VK_SUCCESS;
}
static VKAPI_ATTR VkResult VKAPI_CALL test_create_device(
    VkPhysicalDevice physical, const VkDeviceCreateInfo *info,
    const VkAllocationCallbacks *alloc, VkDevice *output)
{
    VkLayerDeviceLink link = {.pfnNextGetInstanceProcAddr=lower_gipa,
                             .pfnNextGetDeviceProcAddr=host_gdpa};
    VkLayerDeviceCreateInfo chain = {.sType=VK_STRUCTURE_TYPE_LOADER_DEVICE_CREATE_INFO,
        .pNext=info->pNext, .function=VK_LAYER_LINK_INFO, .u.pLayerInfo=&link};
    VkLayerDeviceCreateInfo callback = {.sType=VK_STRUCTURE_TYPE_LOADER_DEVICE_CREATE_INFO,
        .pNext=&chain, .function=VK_LOADER_DATA_CALLBACK, .u.pfnSetDeviceLoaderData=device_loader_data};
    VkDeviceCreateInfo copied = *info;
    copied.pNext = &callback;
    VkResult result = ((PFN_vkCreateDevice)layer_gipa(instance, "vkCreateDevice"))(
        physical, &copied, alloc, output);
    if (result != VK_SUCCESS) return result;
#define AFMF_TEST_FUNCTION(name) do { \
    PFN_vkVoidFunction function = layer_gdpa(*output, #name); \
    if (function) win_##name = (PFN_##name)function; \
} while (0);
#include "windows_harness_functions.inc"
#undef AFMF_TEST_FUNCTION
    win_vkGetInstanceProcAddr = layer_gipa;
    return result;
}
static VKAPI_ATTR VkResult VKAPI_CALL test_create_instance(
    const VkInstanceCreateInfo *info, const VkAllocationCallbacks *alloc, VkInstance *output)
{
    VkLayerInstanceLink link = {.pfnNextGetInstanceProcAddr=lower_gipa};
    VkLayerInstanceCreateInfo chain = {.sType=VK_STRUCTURE_TYPE_LOADER_INSTANCE_CREATE_INFO,
        .pNext=info->pNext, .function=VK_LAYER_LINK_INFO, .u.pLayerInfo=&link};
    VkInstanceCreateInfo copied = *info;
    copied.pNext = &chain;
    VkResult result = ((PFN_vkCreateInstance)layer_gipa(NULL, "vkCreateInstance"))(&copied, alloc, output);
    if (result != VK_SUCCESS) return result;
    instance = *output;
#define AFMF_TEST_FUNCTION(name) do { \
    PFN_vkVoidFunction function = layer_gipa(instance, #name); \
    if (function) win_##name = (PFN_##name)function; \
} while (0);
#include "windows_harness_functions.inc"
#undef AFMF_TEST_FUNCTION
    host_gdpa = (PFN_vkGetDeviceProcAddr)host_gipa(instance, "vkGetDeviceProcAddr");
    win_vkCreateDevice = test_create_device;
    win_vkGetInstanceProcAddr = layer_gipa;
    return result;
}
static VKAPI_ATTR VkResult VKAPI_CALL test_enumerate_layers(uint32_t *count, VkLayerProperties *props)
{
    /* Advertise only the explicitly loaded test layer, never host validation. */
    if (!props) { *count=1; return VK_SUCCESS; }
    if (!*count) return VK_INCOMPLETE;
    memset(props, 0, sizeof *props);
    strcpy(props->layerName, "VK_LAYER_AFMF");
    strcpy(props->description, "Manually chained Windows AFMF DLL under Wine (synthetic test)");
    props->specVersion = VK_API_VERSION_1_1;
    *count=1;
    return VK_SUCCESS;
}
int afmf_test_bridge_initialize(void)
{
    const char *path = getenv("AFMF_TEST_LAYER_DLL");
    if (!path) { fputs("AFMF_TEST_LAYER_DLL is required\n", stderr); return 0; }
    HMODULE host = LoadLibraryA("vulkan-1.dll"), layer = LoadLibraryA(path);
    if (!host || !layer) { fprintf(stderr, "LoadLibrary failed: %lu\n", GetLastError()); return 0; }
    host_gipa = (PFN_vkGetInstanceProcAddr)load_command(host, "vkGetInstanceProcAddr");
    PFN_vkNegotiateLoaderLayerInterfaceVersion negotiate =
        (PFN_vkNegotiateLoaderLayerInterfaceVersion)load_command(layer, "vkNegotiateLoaderLayerInterfaceVersion");
    VkNegotiateLayerInterface interface = {.sType=LAYER_NEGOTIATE_INTERFACE_STRUCT,
                                          .loaderLayerInterfaceVersion=2};
    if (!host_gipa || !negotiate || negotiate(&interface) != VK_SUCCESS) return 0;
    layer_gipa=interface.pfnGetInstanceProcAddr;
    layer_gdpa=interface.pfnGetDeviceProcAddr;
#define AFMF_TEST_FUNCTION(name) win_##name = (PFN_##name)load_command(host, #name);
#include "windows_harness_functions.inc"
#undef AFMF_TEST_FUNCTION
    win_vkEnumerateInstanceLayerProperties=test_enumerate_layers;
    win_vkCreateInstance=test_create_instance;
    fputs("TEST MODE: native Windows DLL manually chained above Wine Vulkan; no native loader claim\n", stderr);
    return 1;
}

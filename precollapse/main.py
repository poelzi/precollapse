from yapsy.PluginManager import PluginManager

from . import db

allPlugins = PluginManager()
# Tell it the default place(s) where to find plugins
allPlugins.setPluginPlaces(["precollapse/plugins"])
# Load all plugins
allPlugins.collectPlugins()

# Activate all loaded plugins
for pluginInfo in allPlugins.getAllPlugins():
    print(pluginInfo)
    print(pluginInfo.name)
    allPlugins.activatePluginByName(pluginInfo.name)
    print(pluginInfo.plugin_object)


__all__ = [allPlugins]

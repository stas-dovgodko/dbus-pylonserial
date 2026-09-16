import QtQuick
import Victron.VenusOS

DeviceListPluginPage {
    id: root

    title: "Pylontech battery monitor"

    GradientListView {
        header: SettingsColumn {
            width: parent ? parent.width : 0

            ListText {
                text: "State of charge"
                dataItem.uid: root.device.serviceUid + "/Soc"
            }
            ListText {
                text: "State of health"
                dataItem.uid: root.device.serviceUid + "/System/Soh"
            }
            ListText {
                text: "Voltage"
                dataItem.uid: root.device.serviceUid + "/Dc/0/Voltage"
            }
            ListText {
                text: "Current"
                dataItem.uid: root.device.serviceUid + "/Dc/0/Current"
            }
            ListText {
                text: "Power"
                dataItem.uid: root.device.serviceUid + "/Dc/0/Power"
            }
            ListText {
                text: "Temperature"
                dataItem.uid: root.device.serviceUid + "/Dc/0/Temperature"
            }
            ListText {
                text: "Online modules"
                dataItem.uid: root.device.serviceUid + "/System/NrOfModulesOnline"
            }
            ListText {
                text: "Cell voltage spread"
                dataItem.uid: root.device.serviceUid + "/System/CellVoltageDiff"
            }
        }

        model: 16

        delegate: ListNavigation {
            id: moduleDelegate

            required property int index
            readonly property int moduleNumber: index + 1
            preferredVisible: online.value === 1
            text: "Module " + moduleNumber
            secondaryText: soc.valid
                ? soc.value + "%" + (cycles.valid ? " | " + cycles.value + " cycles" : "")
                : ""
            onClicked: Global.pageManager.pushPage(modulePageComponent, {
                serviceUid: root.device.serviceUid,
                moduleNumber: moduleNumber
            })

            VeQuickItem {
                id: online
                uid: root.device.serviceUid + "/Modules/" + moduleDelegate.moduleNumber + "/Online"
            }
            VeQuickItem {
                id: soc
                uid: root.device.serviceUid + "/Modules/" + moduleDelegate.moduleNumber + "/Soc"
            }
            VeQuickItem {
                id: cycles
                uid: root.device.serviceUid + "/Modules/" + moduleDelegate.moduleNumber + "/Cycles"
            }
        }
    }

    Component {
        id: modulePageComponent

        Page {
            id: modulePage

            required property string serviceUid
            required property int moduleNumber
            readonly property string modulePrefix: serviceUid + "/Modules/" + moduleNumber
            title: "Pylontech module " + moduleNumber

            GradientListView {
                model: VisibleItemModel {
                    ListText { text: "Manufacturer"; dataItem.uid: modulePage.modulePrefix + "/Manufacturer" }
                    ListText { text: "Model"; dataItem.uid: modulePage.modulePrefix + "/Model" }
                    ListText { text: "Serial number"; dataItem.uid: modulePage.modulePrefix + "/Serial" }
                    ListText { text: "Specification"; dataItem.uid: modulePage.modulePrefix + "/Specification" }
                    ListText { text: "Firmware"; dataItem.uid: modulePage.modulePrefix + "/FirmwareVersion" }
                    ListText { text: "Software version"; dataItem.uid: modulePage.modulePrefix + "/SoftwareVersion" }
                    ListText { text: "Boot version"; dataItem.uid: modulePage.modulePrefix + "/BootVersion" }
                    ListText { text: "Communication version"; dataItem.uid: modulePage.modulePrefix + "/CommunicationVersion" }
                    ListText { text: "Hardware"; dataItem.uid: modulePage.modulePrefix + "/HardwareVersion" }
                    ListText { text: "Release date"; dataItem.uid: modulePage.modulePrefix + "/ReleaseDate" }
                    ListText { text: "EPON port rate"; dataItem.uid: modulePage.modulePrefix + "/EponPortRate" }
                    ListText { text: "Console port rate"; dataItem.uid: modulePage.modulePrefix + "/ConsolePortRate" }
                    ListText { text: "Cycles"; dataItem.uid: modulePage.modulePrefix + "/Cycles" }
                    ListText { text: "State of health"; dataItem.uid: modulePage.modulePrefix + "/Soh" }
                    ListText { text: "State of charge"; dataItem.uid: modulePage.modulePrefix + "/Soc" }
                    ListText { text: "Voltage"; dataItem.uid: modulePage.modulePrefix + "/Voltage" }
                    ListText { text: "Current"; dataItem.uid: modulePage.modulePrefix + "/Current" }
                    ListText { text: "Temperature"; dataItem.uid: modulePage.modulePrefix + "/Temperature" }
                    ListText { text: "State"; dataItem.uid: modulePage.modulePrefix + "/State" }
                    ListText { text: "Voltage state"; dataItem.uid: modulePage.modulePrefix + "/VoltageState" }
                    ListText { text: "Current state"; dataItem.uid: modulePage.modulePrefix + "/CurrentState" }
                    ListText { text: "Temperature state"; dataItem.uid: modulePage.modulePrefix + "/TemperatureState" }
                    ListText { text: "Battery voltage state"; dataItem.uid: modulePage.modulePrefix + "/BatteryVoltageState" }
                    ListText { text: "Battery temperature state"; dataItem.uid: modulePage.modulePrefix + "/BatteryTemperatureState" }
                    ListText { text: "System alarm state"; dataItem.uid: modulePage.modulePrefix + "/SystemAlarmState" }
                    ListText { text: "BMS timestamp"; dataItem.uid: modulePage.modulePrefix + "/Timestamp" }
                    ListText { text: "Maximum charge current"; dataItem.uid: modulePage.modulePrefix + "/MaxChargeCurrent" }
                    ListText { text: "Maximum discharge current"; dataItem.uid: modulePage.modulePrefix + "/MaxDischargeCurrent" }
                    ListText { text: "Remaining capacity"; dataItem.uid: modulePage.modulePrefix + "/RemainingCapacity" }
                    ListText { text: "Cell count"; dataItem.uid: modulePage.modulePrefix + "/CellCount" }
                    ListText { text: "Minimum cell voltage"; dataItem.uid: modulePage.modulePrefix + "/MinCellVoltage" }
                    ListText { text: "Minimum cell number"; dataItem.uid: modulePage.modulePrefix + "/MinCellId" }
                    ListText { text: "Maximum cell voltage"; dataItem.uid: modulePage.modulePrefix + "/MaxCellVoltage" }
                    ListText { text: "Maximum cell number"; dataItem.uid: modulePage.modulePrefix + "/MaxCellId" }
                    ListText { text: "Cell voltage spread"; dataItem.uid: modulePage.modulePrefix + "/CellVoltageDiff" }
                    ListText { text: "Minimum temperature"; dataItem.uid: modulePage.modulePrefix + "/MinTemperature" }
                    ListText { text: "Minimum temperature sensor"; dataItem.uid: modulePage.modulePrefix + "/MinTemperatureSensor" }
                    ListText { text: "Maximum temperature"; dataItem.uid: modulePage.modulePrefix + "/MaxTemperature" }
                    ListText { text: "Maximum temperature sensor"; dataItem.uid: modulePage.modulePrefix + "/MaxTemperatureSensor" }
                    ListText { text: "MOS temperature"; dataItem.uid: modulePage.modulePrefix + "/MosTemperature" }
                    ListText { text: "MOS temperature state"; dataItem.uid: modulePage.modulePrefix + "/MosTemperatureState" }
                    ListNavigation {
                        text: "Statistics and lifetime counters"
                        onClicked: Global.pageManager.pushPage(statisticsPageComponent, {
                            serviceUid: modulePage.serviceUid,
                            moduleNumber: modulePage.moduleNumber
                        })
                    }

                    ListNavigation {
                        text: "Cells"
                        onClicked: Global.pageManager.pushPage(cellsPageComponent, {
                            serviceUid: modulePage.serviceUid,
                            moduleNumber: modulePage.moduleNumber
                        })
                    }
                }
            }
        }
    }

    Component {
        id: statisticsPageComponent

        Page {
            id: statisticsPage

            required property string serviceUid
            required property int moduleNumber
            readonly property string statisticsPrefix: serviceUid + "/Modules/" + moduleNumber + "/Statistics"
            title: "Module " + moduleNumber + " statistics"

            GradientListView {
                model: VisibleItemModel {
                    ListText { text: "Cycles"; dataItem.uid: statisticsPage.statisticsPrefix + "/Cycles" }
                    ListText { text: "State of health"; dataItem.uid: statisticsPage.statisticsPrefix + "/Soh" }
                    ListText { text: "Statistics SOC"; dataItem.uid: statisticsPage.statisticsPrefix + "/Soc" }
                    ListText { text: "Data items"; dataItem.uid: statisticsPage.statisticsPrefix + "/DataItems" }
                    ListText { text: "History items"; dataItem.uid: statisticsPage.statisticsPrefix + "/HistoryItems" }
                    ListText { text: "Charge count"; dataItem.uid: statisticsPage.statisticsPrefix + "/ChargeCount" }
                    ListText { text: "Discharge count"; dataItem.uid: statisticsPage.statisticsPrefix + "/DischargeCount" }
                    ListText { text: "Charge time counter"; dataItem.uid: statisticsPage.statisticsPrefix + "/ChargeTimes" }
                    ListText { text: "Status count"; dataItem.uid: statisticsPage.statisticsPrefix + "/StatusCount" }
                    ListText { text: "Idle time counter"; dataItem.uid: statisticsPage.statisticsPrefix + "/IdleTimes" }
                    ListText { text: "COC count"; dataItem.uid: statisticsPage.statisticsPrefix + "/CocTimes" }
                    ListText { text: "COC2 count"; dataItem.uid: statisticsPage.statisticsPrefix + "/Coc2Times" }
                    ListText { text: "DOC count"; dataItem.uid: statisticsPage.statisticsPrefix + "/DocTimes" }
                    ListText { text: "DOC2 count"; dataItem.uid: statisticsPage.statisticsPrefix + "/Doc2Times" }
                    ListText { text: "COCA count"; dataItem.uid: statisticsPage.statisticsPrefix + "/CocaTimes" }
                    ListText { text: "DOCA count"; dataItem.uid: statisticsPage.statisticsPrefix + "/DocaTimes" }
                    ListText { text: "Short-circuit count"; dataItem.uid: statisticsPage.statisticsPrefix + "/ShortCircuitTimes" }
                    ListText { text: "Battery over-voltage count"; dataItem.uid: statisticsPage.statisticsPrefix + "/BatteryOverVoltageTimes" }
                    ListText { text: "Battery high-voltage count"; dataItem.uid: statisticsPage.statisticsPrefix + "/HighVoltageCount" }
                    ListText { text: "Battery low-voltage count"; dataItem.uid: statisticsPage.statisticsPrefix + "/LowVoltageCount" }
                    ListText { text: "Battery under-voltage count"; dataItem.uid: statisticsPage.statisticsPrefix + "/BatteryUnderVoltageTimes" }
                    ListText { text: "Battery sleep count"; dataItem.uid: statisticsPage.statisticsPrefix + "/BatterySleepTimes" }
                    ListText { text: "Power over-voltage count"; dataItem.uid: statisticsPage.statisticsPrefix + "/PowerOverVoltageTimes" }
                    ListText { text: "Power high-voltage count"; dataItem.uid: statisticsPage.statisticsPrefix + "/PowerHighVoltageTimes" }
                    ListText { text: "Power low-voltage count"; dataItem.uid: statisticsPage.statisticsPrefix + "/PowerLowVoltageTimes" }
                    ListText { text: "Power under-voltage count"; dataItem.uid: statisticsPage.statisticsPrefix + "/PowerUnderVoltageTimes" }
                    ListText { text: "Power sleep count"; dataItem.uid: statisticsPage.statisticsPrefix + "/PowerSleepTimes" }
                    ListText { text: "Charge over-temperature count"; dataItem.uid: statisticsPage.statisticsPrefix + "/ChargeOverTemperatureTimes" }
                    ListText { text: "Charge under-temperature count"; dataItem.uid: statisticsPage.statisticsPrefix + "/ChargeUnderTemperatureTimes" }
                    ListText { text: "Discharge over-temperature count"; dataItem.uid: statisticsPage.statisticsPrefix + "/DischargeOverTemperatureTimes" }
                    ListText { text: "Discharge under-temperature count"; dataItem.uid: statisticsPage.statisticsPrefix + "/DischargeUnderTemperatureTimes" }
                    ListText { text: "Charge high-temperature count"; dataItem.uid: statisticsPage.statisticsPrefix + "/ChargeHighTemperatureTimes" }
                    ListText { text: "Charge low-temperature count"; dataItem.uid: statisticsPage.statisticsPrefix + "/ChargeLowTemperatureTimes" }
                    ListText { text: "Discharge high-temperature count"; dataItem.uid: statisticsPage.statisticsPrefix + "/DischargeHighTemperatureTimes" }
                    ListText { text: "Discharge low-temperature count"; dataItem.uid: statisticsPage.statisticsPrefix + "/DischargeLowTemperatureTimes" }
                    ListText { text: "Shutdown count"; dataItem.uid: statisticsPage.statisticsPrefix + "/ShutdownCount" }
                    ListText { text: "Reset count"; dataItem.uid: statisticsPage.statisticsPrefix + "/ResetCount" }
                    ListText { text: "Reverse-voltage count"; dataItem.uid: statisticsPage.statisticsPrefix + "/ReverseVoltageTimes" }
                    ListText { text: "Input over-voltage count"; dataItem.uid: statisticsPage.statisticsPrefix + "/InputOverVoltageTimes" }
                    ListText { text: "SOH event count"; dataItem.uid: statisticsPage.statisticsPrefix + "/SohTimes" }
                    ListText { text: "BMIC error count"; dataItem.uid: statisticsPage.statisticsPrefix + "/BmicErrorCount" }
                    ListText { text: "Power coulomb (raw)"; dataItem.uid: statisticsPage.statisticsPrefix + "/PowerCoulombRaw" }
                    ListText { text: "Discharge capacity (raw)"; dataItem.uid: statisticsPage.statisticsPrefix + "/DischargeCapacityRaw" }
                    ListText { text: "High-temperature at 0.5C count"; dataItem.uid: statisticsPage.statisticsPrefix + "/HighTemperatureHalfCCount" }
                    ListText { text: "Low-temperature at 0.5C count"; dataItem.uid: statisticsPage.statisticsPrefix + "/LowTemperatureHalfCCount" }
                    ListText { text: "High-temperature count"; dataItem.uid: statisticsPage.statisticsPrefix + "/HighTemperatureCount" }
                    ListText { text: "Low-temperature count"; dataItem.uid: statisticsPage.statisticsPrefix + "/LowTemperatureCount" }
                    ListText { text: "Low-voltage diagnostic count"; dataItem.uid: statisticsPage.statisticsPrefix + "/LowVoltageCountRaw" }
                    ListText { text: "Lifetime warning count"; dataItem.uid: statisticsPage.statisticsPrefix + "/LifeWarningCount" }
                    ListText { text: "Lifetime alarm count"; dataItem.uid: statisticsPage.statisticsPrefix + "/LifeAlarmCount" }
                }
            }
        }
    }

    Component {
        id: cellsPageComponent

        Page {
            id: cellsPage

            required property string serviceUid
            required property int moduleNumber
            readonly property string modulePrefix: serviceUid + "/Modules/" + moduleNumber
            title: "Module " + moduleNumber + " cells"

            GradientListView {
                model: 16

                delegate: ListNavigation {
                    id: cellDelegate

                    required property int index
                    readonly property int cellNumber: index + 1
                    readonly property string cellPrefix: cellsPage.modulePrefix + "/Cells/" + cellNumber
                    preferredVisible: voltage.valid
                    text: "Cell " + cellNumber
                    secondaryText: voltage.valid
                        ? Number(voltage.value).toFixed(3) + " V"
                            + (temperature.valid ? " | " + Number(temperature.value).toFixed(1) + " C" : "")
                            + (balancing.valid && Number(balancing.value) === 1 ? " | balancing" : "")
                        : ""
                    onClicked: Global.pageManager.pushPage(cellPageComponent, {
                        serviceUid: cellsPage.serviceUid,
                        moduleNumber: cellsPage.moduleNumber,
                        cellNumber: cellNumber
                    })

                    VeQuickItem {
                        id: voltage
                        uid: cellDelegate.cellPrefix + "/Voltage"
                    }
                    VeQuickItem {
                        id: temperature
                        uid: cellDelegate.cellPrefix + "/Temperature"
                    }
                    VeQuickItem {
                        id: balancing
                        uid: cellDelegate.cellPrefix + "/Balancing"
                    }
                }
            }
        }
    }

    Component {
        id: cellPageComponent

        Page {
            id: cellPage

            required property string serviceUid
            required property int moduleNumber
            required property int cellNumber
            readonly property string cellPrefix: serviceUid + "/Modules/" + moduleNumber + "/Cells/" + cellNumber
            title: "Module " + moduleNumber + " cell " + cellNumber

            GradientListView {
                model: VisibleItemModel {
                    ListText { text: "Voltage"; dataItem.uid: cellPage.cellPrefix + "/Voltage" }
                    ListText { text: "Current"; dataItem.uid: cellPage.cellPrefix + "/Current" }
                    ListText { text: "Temperature"; dataItem.uid: cellPage.cellPrefix + "/Temperature" }
                    ListText { text: "State of charge"; dataItem.uid: cellPage.cellPrefix + "/Soc" }
                    ListText { text: "Remaining capacity"; dataItem.uid: cellPage.cellPrefix + "/RemainingCapacity" }
                    ListText { text: "Balancing"; dataItem.uid: cellPage.cellPrefix + "/Balancing" }
                    ListText { text: "State"; dataItem.uid: cellPage.cellPrefix + "/State" }
                    ListText { text: "Voltage state"; dataItem.uid: cellPage.cellPrefix + "/VoltageState" }
                    ListText { text: "Current state"; dataItem.uid: cellPage.cellPrefix + "/CurrentState" }
                    ListText { text: "Temperature state"; dataItem.uid: cellPage.cellPrefix + "/TemperatureState" }
                }
            }
        }
    }
}

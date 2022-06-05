from ibapi.client import EClient
from ibapi.wrapper import EWrapper
import pandas as pd

# all callback functions in EWrapper and EClient for connection
class TradeApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.data = {}
        self.pos_df = pd.DataFrame(
            columns=["Account", "Symbol", "SecType", "Currency", "Position", "Avg cost"]
        )
        self.order_df = pd.DataFrame(
            columns=[
                "PermId",
                "ClientId",
                "OrderId",
                "Account",
                "Symbol",
                "SecType",
                "Exchange",
                "Action",
                "OrderType",
                "TotalQty",
                "CashQty",
                "LmtPrice",
                "AuxPrice",
                "Status",
            ]
        )

    def historicalData(self, reqId, bar):
        # print(f'Time: {bar.date}, Open: {bar.open}, Close: {bar.close}')
        if reqId not in self.data:
            self.data[reqId] = [
                {
                    "Date": bar.date,
                    "Open": bar.open,
                    "High": bar.high,
                    "Low": bar.low,
                    "Close": bar.close,
                    "Volume": bar.volume,
                }
            ]
        else:
            self.data[reqId].append(
                {
                    "Date": bar.date,
                    "Open": bar.open,
                    "High": bar.high,
                    "Low": bar.low,
                    "Close": bar.close,
                    "Volume": bar.volume,
                }
            )

    def nextValidId(self, orderId):
        super().nextValidId(orderId)
        self.nextValidOrderId = orderId
        print("NextValidId:", orderId)

    def position(self, account, contract, position, avgCost):
        super().position(account, contract, position, avgCost)
        dictionary = {
            "Account": account,
            "Symbol": contract.symbol,
            "SecType": contract.secType,
            "Currency": contract.currency,
            "Position": position,
            "Avg cost": avgCost,
        }
        self.pos_df = self.pos_df.append(dictionary, ignore_index=True)

    def positionEnd(self):
        print("Latest position data extracted")

    def openOrder(self, orderId, contract, order, orderState):
        super().openOrder(orderId, contract, order, orderState)
        dictionary = {
            "PermId": order.permId,
            "ClientId": order.clientId,
            "OrderId": orderId,
            "Account": order.account,
            "Symbol": contract.symbol,
            "SecType": contract.secType,
            "Exchange": contract.exchange,
            "Action": order.action,
            "OrderType": order.orderType,
            "TotalQty": order.totalQuantity,
            "CashQty": order.cashQty,
            "LmtPrice": order.lmtPrice,
            "AuxPrice": order.auxPrice,
            "Status": orderState.status,
        }
        self.order_df = self.order_df.append(dictionary, ignore_index=True)

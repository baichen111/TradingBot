from TradeApp import TradeApp

from ibapi.contract import Contract
from ibapi.order import Order
import pandas as pd
import threading
import time


class Macd_stoch:
    def __init__(
        self,
        tickers=[
            "FB",
            "AMZN",
            "MSFT",
            "AAPL",
            "GOOG",
            "NVDA",
            "AMD",
            "PLTR",
            "DDOG",
            "SE",
            "U",
            "SHOP",
            "TSLA",
        ],
        capital=1000,candle_interval= 15              #  set 15 mins for each candle
    ):
        self.tickers = tickers
        self.capital = capital
        self.candle_interval = candle_interval

        self.app = TradeApp()
        self.app.connect(host="127.0.0.1", port=7497, clientId=23)
        con_thread = threading.Thread(
            target=self.websocket_con, daemon=True
        )  # a thread for connecting to TWS
        con_thread.start()

    def usTechStk(symbol, sec_type="STK", currency="USD", exchange="ISLAND"):
        contract = Contract()
        contract.symbol = symbol
        contract.secType = sec_type
        contract.currency = currency
        contract.exchange = exchange
        return contract

    # EClient function to request contract details
    def histData(self, req_num, contract, duration, candle_size):
        """extracts historical data"""
        self.app.reqHistoricalData(
            reqId=req_num,
            contract=contract,
            endDateTime="",
            durationStr=duration,
            barSizeSetting=candle_size,
            whatToShow="ADJUSTED_LAST",
            useRTH=1,
            formatDate=1,
            keepUpToDate=0,
            chartOptions=[],
        )

    def websocket_con(self):
        self.app.run()

    ###################storing trade app object in dataframe#######################
    def dataDataframe(self, TradeApp_obj, symbols, symbol):
        "returns extracted historical data in dataframe format"
        df = pd.DataFrame(TradeApp_obj.data[symbols.index(symbol)])
        df.set_index("Date", inplace=True)
        return df

    def MACD(self, DF, a=12, b=26, c=9):
        """function to calculate MACD typical values
        a(fast moving average) = 12;
        b(slow moving average) =26;
        c(signal line ma window) =9"""
        df = DF.copy()
        df["MA_Fast"] = df["Close"].ewm(span=a, min_periods=a).mean()
        df["MA_Slow"] = df["Close"].ewm(span=b, min_periods=b).mean()
        df["MACD"] = df["MA_Fast"] - df["MA_Slow"]
        df["Signal"] = df["MACD"].ewm(span=c, min_periods=c).mean()
        return df

    def stochOscltr(self, DF, a=20, b=3):
        """function to calculate Stochastics
        a = lookback period
        b = moving average window for %D"""
        df = DF.copy()
        df["C-L"] = df["Close"] - df["Low"].rolling(a).min()
        df["H-L"] = df["High"].rolling(a).max() - df["Low"].rolling(a).min()
        df["%K"] = df["C-L"] / df["H-L"] * 100
        # df['%D'] = df['%K'].ewm(span=b,min_periods=b).mean()
        return df["%K"].rolling(b).mean()

    def atr(self, DF, n):
        "function to calculate True Range and Average True Range"
        df = DF.copy()
        df["H-L"] = abs(df["High"] - df["Low"])
        df["H-PC"] = abs(df["High"] - df["Close"].shift(1))
        df["L-PC"] = abs(df["Low"] - df["Close"].shift(1))
        df["TR"] = df[["H-L", "H-PC", "L-PC"]].max(axis=1, skipna=False)
        # df['ATR'] = df['TR'].rolling(n).mean()
        df["ATR"] = df["TR"].ewm(com=n, min_periods=n).mean()
        return df["ATR"]

    def marketOrder(self, direction, quantity):
        order = Order()
        order.action = direction
        order.orderType = "MKT"
        order.totalQuantity = quantity
        order.tif = "IOC"
        return order

    def stopOrder(self, direction, quantity, st_price):
        order = Order()
        order.action = direction
        order.orderType = "STP"
        order.totalQuantity = quantity
        order.auxPrice = st_price
        return order
    
    def strategyLogic(self,period = '1 M'):
        #request positions
        self.app.reqPositions()
        time.sleep(2)
        pos_df = self.app.pos_df
        pos_df.drop_duplicates(inplace=True,ignore_index=True) # position callback may give duplicate values
        
        #request open orders
        self.app.reqOpenOrders()
        time.sleep(2)
        ord_df = self.app.order_df
        
        #interate each ticker for trading logic
        candle_interval = " ".join([str(self.candle_interval),"mins"])
        for ticker in self.tickers:
            print("starting requesting data for.....",ticker)
            self.histData(self.tickers.index(ticker),self.usTechStk(ticker),period, candle_interval)
            time.sleep(5)
            df = self.dataDataframe(self.app,self.tickers,ticker)
            df["stoch"] = self.stochOscltr(df)
            df["macd"] = self.MACD(df)["MACD"]
            df["signal"] = self.MACD(df)["Signal"]
            df["atr"] = self.atr(df,60)
            df.dropna(inplace=True)
            
            #trading quantity
            quantity = int(self.capital/df["Close"][-1])
            if quantity == 0:
                continue
            
            #trading logic
            if len(pos_df.columns)==0: # if no position
                if df["macd"][-1]> df["signal"][-1] and df["stoch"][-1]> 30 and df["stoch"][-1] > df["stoch"][-2]:
                   self.app.reqIds(-1)
                   time.sleep(2)
                   order_id = self.app.nextValidOrderId
                   self.app.placeOrder(order_id,self.usTechStk(ticker),self.marketOrder("BUY",quantity))
                   time.sleep(5)
                   try:
                       pos_df = self.app.pos_df
                       time.sleep(5)
                       sl_q = pos_df[pos_df["Symbol"]==ticker]["Position"].sort_values(ascending=True).values[-1]
                       self.app.placeOrder(order_id+1,self.usTechStk(ticker),self.stopOrder("SELL",sl_q,round(df["Close"][-1]-df["atr"][-1],1)))
                   except Exception as e:
                        print(e, "no fill for {}".format(ticker))
          
            elif len(pos_df.columns)!=0 and ticker not in pos_df["Symbol"].tolist(): # if got position but current ticker is not in the position
                if df["macd"][-1]> df["signal"][-1] and df["stoch"][-1]> 30 and df["stoch"][-1] > df["stoch"][-2]:
                    self.app.reqIds(-1)
                    time.sleep(2)
                    order_id = self.app.nextValidOrderId
                    self.app.placeOrder(order_id,self.usTechStk(ticker),self.marketOrder("BUY",quantity))
                    time.sleep(5)
                    try:
                        pos_df = self.app.pos_df
                        time.sleep(5)
                        sl_q = pos_df[pos_df["Symbol"]==ticker]["Position"].sort_values(ascending=True).values[-1]
                        self.app.placeOrder(order_id+1,self.usTechStk(ticker),self.stopOrder("SELL",sl_q,round(df["Close"][-1]-df["atr"][-1],1)))
                    except Exception as e:
                            print(e, "no fill for {}".format(ticker))
                    
            elif len(pos_df.columns)!=0 and ticker in pos_df["Symbol"].tolist(): # if got position and ticker is in position
                if pos_df[pos_df["Symbol"]==ticker]["Position"].sort_values(ascending=True).values[-1] == 0: #ticker position value is 0
                    if df["macd"][-1]> df["signal"][-1] and df["stoch"][-1]> 30 and df["stoch"][-1] > df["stoch"][-2]:
                        self.app.reqIds(-1)
                        time.sleep(2)
                        order_id = self.app.nextValidOrderId
                        self.app.placeOrder(order_id,self.usTechStk(ticker),self.marketOrder("BUY",quantity))
                        time.sleep(5)
                        try:
                            pos_df = self.app.pos_df
                            time.sleep(5)
                            sl_q = pos_df[pos_df["Symbol"]==ticker]["Position"].sort_values(ascending=True).values[-1]
                            self.app.placeOrder(order_id+1,self.usTechStk(ticker),self.stopOrder("SELL",sl_q,round(df["Close"][-1]-df["atr"][-1],1)))
                        except Exception as e:
                                print(e, "no fill for {}".format(ticker))
                elif pos_df[pos_df["Symbol"]==ticker]["Position"].sort_values(ascending=True).values[-1] > 0: #ticker position value is more than 0
                    try:
                        ord_id = ord_df[ord_df["Symbol"]==ticker]["OrderId"].sort_values(ascending=True).values[-1]
                        old_quantity = pos_df[pos_df["Symbol"]==ticker]["Position"].sort_values(ascending=True).values[-1]
                        self.app.cancelOrder(ord_id)
                        self.app.reqIds(-1)
                        time.sleep(2)
                        order_id = self.app.nextValidOrderId
                        self.app.placeOrder(order_id,self.usTechStk(ticker),self.stopOrder("SELL",old_quantity,round(df["Close"][-1]-df["atr"][-1],1)))
                    except Exception as e:
                        print(ticker,e)
        
    def run(self,duration = 60*60*6,candle_interval = 15): #duration: how long do we want to run the programme
        starttime = time.time()
        endtime = time.time() + duration
        while time.time() <= endtime:
            self.strategyLogic()
            time.sleep(60*candle_interval - ((time.time() - starttime) % 60*candle_interval))
            
if __name__ == '__main__':
    myTradingApp = Macd_stoch()
    myTradingApp.run()
        

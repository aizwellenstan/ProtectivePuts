# region imports
from AlgorithmImports import *
# endregion
############################################################
# Long SPY shares with flexible share-to-put ratio at 60 DTE, rolled at 30 days.
############################################################
from datetime import timedelta
from OptionsUtil import *

class LongSPYOTMPut(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2020, 3, 18)
        self.SetCash(100000)
        self.symbol = "QQQ"  # Keep the instrument symbol in a variable
        self.equity = self.AddEquity(self.symbol, Resolution.Minute)
        self.SPYSymbol = self.equity.Symbol
        self.InitParameters()
        self.OptionsUtil = OptionsUtil(self, self.equity)

    ## Initialize parameters (periods, days-till-expiration, etc)
    ## ------------------------------------------------------------
    def InitParameters(self):
        self.putExpiryDate     = None
        self.putInitialDTE     = 60
        self.putExitDTECoeff   = 0.5
        self.putStrikeDelta    = -0.50
        self.sharesPerPut      = 100  # Number of shares per 1 put
        self.estimatedFee      = 1.00  # Estimated fee per transaction
        
        self.Schedule.On(self.DateRules.EveryDay(self.SPYSymbol),
                         self.TimeRules.AfterMarketOpen(self.SPYSymbol, 30),
                         self.DailyAtMarketOpen)

    ## Every morning at market open, Check for entries / exits.
    ## ------------------------------------------------------------
    def DailyAtMarketOpen(self):
        if not self.IsWarmingUp and self.CurrentSlice.ContainsKey(self.symbol):
            putsInPortfolio = len([x for x in self.Portfolio if (x.Value.Symbol.HasUnderlying and x.Value.Invested)])

            if not self.Portfolio.Invested or (putsInPortfolio == 0):
                self.SetSharesHoldings()
                self.BuyOTMPuts()

            elif self.Portfolio.Invested:
                currentDTE = (self.putExpiryDate - self.Time).days
                if currentDTE <= (self.putInitialDTE * self.putExitDTECoeff):
                    for x in self.Portfolio:
                        if x.Value.Invested:
                            assetLabel  = "Puts" if x.Value.Symbol.HasUnderlying else "Shares"
                            assetChange = round(self.Portfolio[x.Value.Symbol].UnrealizedProfitPercent, 2)
                            profitLabel = "Profit" if assetChange > 0 else "Loss"
                            if x.Value.Symbol.HasUnderlying:
                                self.Liquidate(x.Value.Symbol, tag=f" {currentDTE} DTE. Sold {assetLabel} [ {assetChange}% {profitLabel} ]")

    ## Allocate capital to SPY shares based on the share-to-put ratio
    ## ------------------------------------------------------------
    def SetSharesHoldings(self):
        if self.CurrentSlice.ContainsKey(self.SPYSymbol) and (self.CurrentSlice[self.SPYSymbol] is not None):
            currentSpyPrice = self.CurrentSlice[self.SPYSymbol].Price
            availableCash = self.Portfolio.Cash - self.estimatedFee  # Subtract estimated fee
            sharesToBuy = (availableCash // (currentSpyPrice * self.sharesPerPut)) * self.sharesPerPut
            totalCost = sharesToBuy * currentSpyPrice

            if sharesToBuy > 0 and availableCash >= totalCost:
                self.SetHoldings(self.symbol, totalCost / self.Portfolio.TotalPortfolioValue, tag=f"Bought {sharesToBuy} {self.symbol} shares.")
            else:
                self.Liquidate()
                self.Log(f"{self.Time} [Warning] Not enough cash to buy a multiple of {self.sharesPerPut} {self.symbol} shares.")

    ## Buy OTM Puts based on the number of shares held
    ## ------------------------------------------------------------
    def BuyOTMPuts(self):
        sharesHeld = self.Portfolio[self.symbol].Quantity
        putsToBuy = round(sharesHeld // self.sharesPerPut) + 1

        if putsToBuy > 0:
            putContract = self.OptionsUtil.SelectContractByDelta(self.SPYSymbol, self.putStrikeDelta, self.putInitialDTE, OptionRight.Put)

            if putContract is None:
                return

            putCost = putContract.AskPrice * 100 * putsToBuy

            if self.Portfolio.Cash >= putCost:
                self.Order(putContract.Symbol, putsToBuy, False, f"Bought {putsToBuy} OTM Puts")
                self.putExpiryDate = putContract.Expiry
            else:
                self.Log(f"{self.Time} [Warning] Not enough cash to buy {putsToBuy} Puts.")
                self.Liquidate()
        else:
            self.Log(f"{self.Time} [Warning] Not holding enough {self.symbol} shares for puts. Staying in cash.")
            self.Liquidate()

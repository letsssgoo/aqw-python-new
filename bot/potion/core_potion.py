from bot.core_bots import buy_item
from core.command import Command

"""
# todo
body tonic: buy for shop item id
Unstable Divine Elixir: "Dragon Scale", "Lemurphant Tears"
Unstable Battle Elixir: "Doomatter", "Nimblestem"
Unstable Body Tonic: "Nimblestem", "Roc Tongue"
Unstable Fate Tonic: "Dried Slime", "Trollola Nectar"
Unstable Might Tonic: "Chaos Entity", "Fish Oil"

dragon scale: Adv.BuyItem("alchemyacademy", 397, 11475, ingreQuant, 2, 1232);
nimblestem: Adv.BuyItem("alchemyacademy", 397, 11469, ingreQuant, 2, 1226);
trollola nectar: Adv.BuyItem("alchemyacademy", 397, 11476, ingreQuant, 2, 1233);
fish oil: Adv.BuyItem("alchemyacademy", 397, 11467, ingreQuant, 3, 1224);

public void BuyItem(string map, int shopID, int itemID, int quant = 1, int shopQuant = 1, int shopItemID = 0, bool Log = true)
"""


async def PotentHonorMalice(cmd: Command, qty: int = 300):
    await craft_potion(
        cmd,
        "Potent Honor Potion",
        ["Chaoroot", "Chaos Entity"],
        ("%xt%zm%crafting%1%getAlchWait%11481%11482%true%Ready to Mix%Chaoroot%Chaos Entity%Gebo%Dam%",
         "%xt%zm%crafting%1%checkAlchComplete%11481%11482%true%Mix Complete%Chaoroot%Chaos Entity%Gebo%Dam%"),
        qty
    )
    await craft_potion(
        cmd,
        "Potent Malice Potion",
        ["Chaoroot", "Chaos Entity"],
        ("%xt%zm%crafting%1%getAlchWait%11481%11482%true%Ready to Mix%Chaoroot%Chaos Entity%Gebo%Dam%",
         "%xt%zm%crafting%1%checkAlchComplete%11481%11482%true%Mix Complete%Chaoroot%Chaos Entity%Gebo%Dam%"),
        qty
    )

async def BodyTonic(cmd: Command, qty: int = 300):
    # await craft_potion(
    #     bot,
    #     cmd,
    #     "Body Tonic",
    #     ["Chaoroot", "Roc Tongue"],
    #     ("%xt%zm%crafting%1%getAlchWait%11471%11481%true%Ready to Mix%Roc Tongue%Chaoroot%Gebo%End%",
    #      "%xt%zm%crafting%1%checkAlchComplete%11471%11481%true%Mix Complete%Roc Tongue%Chaoroot%Gebo%End%"),
    #     qty
    # )


    # need to make buy reagent by shop item id
    return

async def FateTonic(cmd: Command, qty: int = 300):
    await craft_potion(
        cmd,
        "Fate Tonic",
        ["Dried Slime", "Arashtite Ore"],
        ("%xt%zm%crafting%1%getAlchWait%11473%11474%true%Ready to Mix%Arashtite Ore%Dried Slime%Gebo%Luc%",
         "%xt%zm%crafting%1%checkAlchComplete%11473%11474%true%Mix Complete%Arashtite Ore%Dried Slime%Gebo%Luc%"),
        qty
    )

async def MightTonic(cmd: Command, qty: int = 300):
    await craft_potion(
        cmd,
        "Might Tonic",
        ["Chaos Entity", "Rhison Blood"],
        ("%xt%zm%crafting%1%getAlchWait%11482%11470%true%Ready to Mix%Chaos Entity%Rhison Blood%Gebo%Dam%",
         "%xt%zm%crafting%1%checkAlchComplete%11482%11470%true%Mix Complete%Chaos Entity%Rhison Blood%Gebo%Dam%"),
        qty
    )

async def PotentDestructionElixir(cmd: Command, qty: int = 300):
    await craft_potion(
        cmd,
        "Potent Destruction Elixir",
        ["Dried Slime", "Arashtite Ore"],
        ("%xt%zm%crafting%1%getAlchWait%11474%11473%true%Ready to Mix%Dried Slime%Arashtite Ore%Gebo%mRe%",
         "%xt%zm%crafting%1%checkAlchComplete%11474%11473%true%Mix Complete%Dried Slime%Arashtite Ore%Gebo%mRe%"),
        qty
    )

async def PotentBattleElixir(cmd: Command, qty: int = 300):
    await craft_potion(
        cmd,
        "Potent Battle Elixir",
        ["Chaoroot", "Doomatter"],
        ("%xt%zm%crafting%1%getAlchWait%11477%11481%true%Ready to Mix%Doomatter%Chaoroot%Gebo%APw%",
         "%xt%zm%crafting%1%checkAlchComplete%11477%11481%true%Mix Complete%Doomatter%Chaoroot%Gebo%APw%"),
        qty
    )

async def PotentMalevolence(cmd: Command, qty: int = 300):
    await craft_potion(
        cmd,
        "Potent Malevolence Elixir",
        ["Chaoroot", "Doomatter"],
        ("%xt%zm%crafting%1%getAlchWait%11477%11481%true%Ready to Mix%Doomatter%Chaoroot%Gebo%SPw%",
         "%xt%zm%crafting%1%checkAlchComplete%11477%11481%true%Mix Complete%Doomatter%Chaoroot%Gebo%SPw%"),
        qty
    )

async def PotentRevitalizeElixir(cmd: Command, qty: int = 300):
    await craft_potion(
        cmd,
        "Potent Revitalize Elixir",
        ["Chaoroot", "Lemurphant Tears"],
        ("%xt%zm%crafting%1%getAlchWait%11481%11479%true%Ready to Mix%Chaoroot%Lemurphant Tears%Gebo%hRe%",
         "%xt%zm%crafting%1%checkAlchComplete%11481%11479%true%Mix Complete%Chaoroot%Lemurphant Tears%Gebo%hRe%"),
        qty
    )

async def SageTonic(cmd: Command, qty: int = 300):
    await craft_potion(
        cmd,
        "Sage Tonic",
        ["Dried Slime", "Arashtite Ore"],
        ("%xt%zm%crafting%1%getAlchWait%11473%11474%true%Ready to Mix%Arashtite Ore%Dried Slime%Gebo%Int%",
         "%xt%zm%crafting%1%checkAlchComplete%11473%11474%true%Mix Complete%Arashtite Ore%Dried Slime%Gebo%Int%"),
        qty
    )

async def template(cmd: Command, qty: int = 300):
    await craft_potion(
        cmd,
        "potion",
        ["ragent1", "reagent2"],
        ("packet1",
         "packet2"),
        qty
    )

async def craft_potion(
    cmd: Command,
    potion_name: str,
    reagents: list[str],
    packets: tuple[str, str],
    qty: int = 300
):
    print(f"\nDOING {potion_name}")
    cmd.farming_logger(potion_name, qty)
    await cmd.bank_to_inv(potion_name)

    cmd.add_drop(potion_name)

    if cmd.get_quant_item(potion_name) >= qty:
        print(f"DONE {potion_name}")
        return

    while cmd.is_still_connected():
        if cmd.get_quant_item(potion_name) >= qty:
            print(f"DONE {potion_name}")
            return

        for reagent in reagents:
            cmd.farming_logger(reagent, 10)
            await get_reagent(cmd, reagent)

        await cmd.join_map("alchemy", 99999999)

        while cmd.is_still_connected():
            if cmd.get_quant_item(potion_name) >= qty:
                return
            if any(cmd.get_quant_item(reagent) < 1 for reagent in reagents):
                break

            print()

            print(f"Trying to make {potion_name}")
            cmd.bot.write_message(packets[0])

            print("Waiting for 12s")
            await cmd.sleep(12000)

            cmd.bot.write_message(packets[1])
            await cmd.sleep(1000)
            print(f"{potion_name} made")

            cmd.farming_logger(potion_name, qty)
    print(f"DONE {potion_name}")
    
async def get_reagent(cmd: Command, reagent: str):
    await cmd.bank_to_inv(reagent)
    if cmd.get_quant_item(reagent) >= 10:
        return
    
    print(f"buying {reagent}...")
    
    if reagent.lower() == "Chaoroot".lower():
        await get_receipt_of_swindle(cmd, 1)
        await buy_from_swindle(cmd, reagent, 10)
    
    elif reagent.lower() == "Doomatter".lower():
        await get_receipt_of_swindle(cmd, 1)
        await buy_from_swindle(cmd, reagent, 10)

    elif reagent.lower() == "Chaos Entity".lower():
        await get_gold_voucher_100k(cmd, 10)
        await buy_from_jera_shop(cmd, reagent, 10)

    elif reagent.lower() == "Dried Slime".lower():
        await buy_dragon_runestone(cmd, 5)
        await buy_alchemy_item(cmd, reagent, 10)
        
    elif reagent.lower() == "Arashtite Ore".lower():
        await buy_dragon_runestone(cmd, 5)
        await buy_alchemy_item(cmd, reagent, 10)

    elif reagent.lower() == "Rhison Blood".lower():
        await buy_dragon_runestone(cmd, 5)
        await buy_alchemy_item(cmd, reagent, 10)

    elif reagent.lower() == "Lemurphant Tears".lower():
        await buy_dragon_runestone(cmd, 5)
        await buy_alchemy_item(cmd, reagent, 10)

    else:
        print(f"bot dont know about {reagent}")
    
    await cmd.sleep(1000)

async def get_receipt_of_swindle(cmd: Command, qty: int = 1):
    await cmd.bank_to_inv("Receipt of Swindle")
    if cmd.get_quant_item("Receipt of Swindle") >= qty:
        return
    await buy_from_swindle(cmd, "Receipt of Swindle", qty)

async def get_gold_voucher_100k(cmd: Command, qty: int = 1):
    await cmd.bank_to_inv("Gold Voucher 100k")
    cmd.farming_logger("Gold Voucher 100k")
    if cmd.get_quant_item("Gold Voucher 100k") >= qty:
        return
    await cmd.join_map("alchemyacademy", 9999999)
    await cmd.ensure_load_shop(2114)
    await buy_item(cmd, 2114, "Gold Voucher 100k", qty)
    cmd.farming_logger("Gold Voucher 100k")
    
async def buy_from_swindle(cmd: Command, itemName: str, qty: int = 10):
    await cmd.bank_to_inv(itemName)
    if cmd.get_quant_item(itemName) >= qty:
        return
    await cmd.join_map("tercessuinotlim", 9999999)
    await cmd.jump_cell("Swindle", "Left")
    await cmd.ensure_load_shop(1951)
    await buy_item(cmd, 1951, itemName, qty)

async def buy_from_jera_shop(cmd: Command, itemName: str, qty: int = 10):
    await cmd.bank_to_inv(itemName)
    if cmd.get_quant_item(itemName) >= qty:
        return
    await cmd.join_map("alchemyacademy", 9999999)
    await cmd.ensure_load_shop(2114)
    await buy_item(cmd, 2114, itemName, qty)

async def buy_dragon_runestone(cmd: Command, qty: int = 1):
    await cmd.bank_to_inv("Dragon Runestone")
    if cmd.get_quant_item("Dragon Runestone") >= qty:
        return
    await get_gold_voucher_100k(cmd, qty)
    await cmd.join_map("alchemyacademy", 9999999)
    await cmd.ensure_load_shop(395)
    await buy_item(cmd, 395, "Dragon Runestone", qty)
    cmd.farming_logger("Gold Voucher 100k")

async def buy_alchemy_item(cmd: Command, itemName: str, qty: int = 10):
    await cmd.bank_to_inv(itemName)
    if cmd.get_quant_item(itemName) >= qty:
        return
    await cmd.join_map("alchemyacademy", 9999999)
    await cmd.ensure_load_shop(397)
    await buy_item(cmd, 397, itemName, qty)
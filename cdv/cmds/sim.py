import asyncio
from pathlib import Path
from typing import Any, Optional

import click
from chia.util.config import load_config

from cdv.cmds.sim_utils import (
    SIMULATOR_ROOT_PATH,
    async_config_wizard,
    execute_with_simulator,
    farm_blocks,
    print_status,
    revert_block_height,
    set_auto_farm,
    start_async,
)


@click.group("sim", short_help="Configure and make requests to a Chia Simulator Full Node")
@click.option(
    "-p",
    "--rpc-port",
    help=(
        "Set the port where the Simulator is hosting the RPC interface. "
        "See the rpc_port under full_node in config.yaml"
    ),
    type=int,
    default=None,
)
@click.option(
    "--root-path", default=SIMULATOR_ROOT_PATH, help="Simulator root folder.", type=click.Path(), show_default=True
)
@click.option(
    "-n",
    "--simulator_name",
    help="This name is used to determine the sub folder to use in the simulator root folder.",
    type=str,
    default="main",
)
@click.pass_context
def sim_cmd(ctx: click.Context, rpc_port: Optional[int], root_path: str, simulator_name: str) -> None:
    ctx.ensure_object(dict)
    ctx.obj["root_path"] = Path(root_path) / simulator_name
    ctx.obj["sim_name"] = simulator_name
    ctx.obj["rpc_port"] = rpc_port


@sim_cmd.command("create", short_help="Guides you through the process of setting up a Chia Simulator")
@click.option("-f", "--fingerprint", type=int, required=False, help="Use your fingerprint to skip the key prompt")
@click.option(
    "-r",
    "--reward_address",
    type=str,
    required=False,
    help="Use this address instead of the default farming address.",
)
@click.option(
    "-p", "--plot-directory", type=str, required=False, help="Use a different directory then 'simulator/plots'."
)
@click.option("-m", "--mnemonic", type=str, required=False, help="Add to keychain and use a specific mnemonic.")
@click.option("-a", "--auto-farm", type=bool, default=None, help="Enable or Disable auto farming")
@click.option(
    "-d",
    "--docker_mode",
    is_flag=True,
    hidden=True,
    help="Run non-interactively in Docker Mode, & generate a new key if keychain is empty.",
)
@click.option("-b", "--no-bitfield", type=bool, is_flag=True, help="Do not use bitfield when generating plots")
@click.pass_context
def create_simulator_config(
    ctx: click.Context,
    fingerprint: Optional[int],
    reward_address: Optional[str],
    plot_directory: Optional[str],
    mnemonic: Optional[str],
    auto_farm: Optional[bool],
    docker_mode: bool,
    no_bitfield: bool,
) -> None:
    print(f"Using this Directory: {ctx.obj['root_path']}\n")
    if fingerprint and mnemonic:
        print("You can't use both a fingerprint and a mnemonic. Please choose one.")
        return None
    asyncio.run(
        async_config_wizard(
            ctx.obj["root_path"],
            fingerprint,
            reward_address,
            plot_directory,
            mnemonic,
            auto_farm,
            docker_mode,
            not no_bitfield,
        )
    )


@sim_cmd.command("start", short_help="Start service groups")
@click.option("-r", "--restart", is_flag=True, help="Restart running services")
@click.option("-w", "--wallet", is_flag=True, help="Start wallet")
@click.pass_context
def start_cmd(ctx: click.Context, restart: bool, wallet: bool) -> None:
    group: Any = ("simulator",)
    if wallet:
        group += ("wallet",)
    asyncio.run(start_async(ctx.obj["root_path"], group, restart))


@sim_cmd.command("stop", short_help="Stop running services")
@click.option("-d", "--daemon", is_flag=True, help="Stop daemon")
@click.option("-w", "--wallet", is_flag=True, help="Stop wallet")
@click.pass_context
def stop_cmd(ctx: click.Context, daemon: bool, wallet: bool) -> None:
    import sys

    from chia.cmds.stop import async_stop

    config = load_config(ctx.obj["root_path"], "config.yaml")
    group: Any = ("simulator",)
    if wallet:
        group += ("wallet",)
    sys.exit(asyncio.run(async_stop(ctx.obj["root_path"], config, group, daemon)))


@sim_cmd.command("status", short_help="Get information about the state of the simulator.")
@click.option("-f", "--fingerprint", type=int, help="Get detailed information on this fingerprint.")
@click.option("-k", "--show_key", is_flag=True, help="Show detailed key information.")
@click.option("-c", "--show_coins", is_flag=True, help="Show all unspent coins.")
@click.option("-i", "--include_rewards", is_flag=True, help="Should show rewards coins?")
@click.option("-a", "--show_addresses", is_flag=True, help="Show the balances of all addresses.")
@click.pass_context
def status_cmd(
    ctx: click.Context,
    fingerprint: Optional[int],
    show_key: bool,
    show_coins: bool,
    include_rewards: bool,
    show_addresses: bool,
) -> None:
    asyncio.run(
        execute_with_simulator(
            ctx.obj["rpc_port"],
            ctx.obj["root_path"],
            print_status,
            True,
            fingerprint,
            show_key,
            show_coins,
            include_rewards,
            show_addresses,
        )
    )


@sim_cmd.command("revert", short_help="Reset chain to a previous block height.")
@click.option("-b", "--blocks", type=int, default=1, help="Number of blocks to go back.")
@click.option("-n", "--new_blocks", type=int, default=1, help="Number of new blocks to add during a reorg.")
@click.option("-r", "--reset", is_flag=True, help="Reset the chain to the genesis block")
@click.option(
    "-f",
    "--force",
    is_flag=True,
    help="Forcefully delete blocks, this is not a reorg but might be needed in very special circumstances."
    "  Note: Use with caution, this will break all wallets.",
)
@click.option("-d", "--disable_prompt", is_flag=True, help="Disable confirmation prompt when force reverting.")
@click.pass_context
def revert_cmd(
    ctx: click.Context, blocks: int, new_blocks: int, reset: bool, force: bool, disable_prompt: bool
) -> None:
    if force and not disable_prompt:
        input_str = (
            "Are you sure you want to force delete blocks? This should only ever be used in special circumstances,"
            " and will break all wallets. \nPress 'y' to continue, or any other button to exit: "
        )
        if input(input_str) != "y":
            return
    if reset and blocks != 1:
        print("\nBlocks, '-b' must not be set if all blocks are selected by reset, '-r'. Exiting.\n")
        return
    asyncio.run(
        execute_with_simulator(
            ctx.obj["rpc_port"],
            ctx.obj["root_path"],
            revert_block_height,
            True,
            blocks,
            new_blocks,
            reset,
            force,
        )
    )


@sim_cmd.command("farm", short_help="Farm blocks")
@click.option("-b", "--blocks", type=int, default=1, help="Amount of blocks to create")
@click.option("-n", "--non-transaction", is_flag=True, help="Allow non-transaction blocks")
@click.option("-a", "--target-address", type=str, default="", help="Block reward address")
@click.pass_context
def farm_cmd(ctx: click.Context, blocks: int, non_transaction: bool, target_address: str) -> None:
    asyncio.run(
        execute_with_simulator(
            ctx.obj["rpc_port"],
            ctx.obj["root_path"],
            farm_blocks,
            True,
            blocks,
            not non_transaction,
            target_address,
        )
    )


@sim_cmd.command("autofarm", short_help="Enable or disable auto farming on transaction submission")
@click.argument("set_autofarm", type=click.Choice(["on", "off"]), nargs=1, required=True)
@click.pass_context
def autofarm_cmd(ctx: click.Context, set_autofarm: str) -> None:
    autofarm = bool(set_autofarm == "on")
    asyncio.run(
        execute_with_simulator(
            ctx.obj["rpc_port"],
            ctx.obj["root_path"],
            set_auto_farm,
            True,
            autofarm,
        )
    )

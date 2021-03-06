"""
Maybe some comments about implementation here.

References to page numbers in this code are referring to the paper:
[1] Price at al. FastTree: Computing Large Minimum Evolution Trees with Profiles instead of a Distance Matrix.
    Molecular Biology and Evolution, vol 26 (7). 2009.
    Paper can be found on https://pubmed.ncbi.nlm.nih.gov/19377059/
"""
import math
import sys
from queue import PriorityQueue
import time

import argparse

from src.node import Node
from src.tree import Tree
import src.heuristics as heuristics
import src.neighbor_joining as neighbor_joining
import src.util as util


def fast_tree(args: argparse.Namespace, sequences: dict) -> str:
    """FastTree Algorithm.

    This main function will follow the steps as discussed in the paper Figure 1:

    0) Not mentioned in the figure, but FastTree first makes sure all sequences are unique (see Unique Sequences)
    1) Create alignment Total Profile T ( Done inside Tree Object )
    2) Initialize Top-Hits (and FastNJ heuristic)
    3) Initial Topology
    4) NNI, containing Log2(N) + 1 rounds of NNIs
    5) Computing the final branch lengths
    6) Returning the Newick String representation of the phylogenetic tree.

    Args:
        args: Namespace of the argparse library, containing all user inputs
        sequences (dict): Mapping of sequences to their names, as was provided in the program's input

    Returns:
        (str): A phylogenetic tree in Newick format.
    """
    # Actual first step : Unique sequences ( page 1646)
    sequences, identical_sequences = uniquify_sequences(sequences)

    # Create list of Nodes representing the sequences
    nodes = []
    for ii, seq in enumerate(sequences.keys()):
        node = Node(seq, ii, sequences[seq], identical_sequences[ii])
        node.leaf = True
        nodes.append(node)

    # Create Tree object
    ft = Tree(nodes, args)

    if ft.verbose == 1:
        print("The names of the {} sequences entered into the program : ".format(len(sequences.items())))
        for key, value in sequences.items():
            print(key)
    if ft.verbose == 2:
        print("The sequences entered into the program : ")
        for key, value in sequences.items():
            print(key, ':', value)

    # Heuristics for neighbor joining (with top-hits)

    # Top hits sequence
    heuristics.TopHits.top_hits_init(ft)

    # Initialize FastNJ Best-hit heuristic
    heuristics.fastNJ_init(ft)

    # End of neighbor joining heuristic preparation

    # Create initial topology
    CreateInitialTopology(ft)
    if ft.verbose == 1:
        ("Initial topology is created containing", len(ft.nodes), "nodes : ")
        ft.newick_str()
        print()

    # Nearest Neighbor Interchanges
    NNI(ft)
    if ft.verbose == 1:
        print("NNI is finished")

    # Calculate branch lengths
    ft.BranchLength()
    
    # Final step: print tree topology as Newick string
    newick = ft.newick_str()

    # Output total runtime in seconds
    end = time.time()
    total_time = end - args.start
    print("Total runtime : ", total_time)

    return newick


def uniquify_sequences(sequences: dict) -> tuple:
    """Make sure sequences are unique, and dupes are made into multifurcating nodes.

    Large alignments often contain many sequences that are exactly identical to each other [18]. FastTree uses
    hashing to quickly identify redundant sequences, constructs a tree for the unique subset of sequences,
    and then creates multifurcating nodes, without support values, as parents of the redundant sequences

    Args:
        sequences (dict) : The mapping of sequences names to their sequences from the input file.

    Returns
        unique_sequences, number_of_duplicates (dict, list)
    """
    unique_sequences = set()
    duplicate_counter = {}

    for name, seq in sequences.items():
        if seq not in unique_sequences:
            unique_sequences.add(seq)
            duplicate_counter[seq] = (name, [name])
        else:
            # Add the name of the duplicate
            duplicate_counter[seq][1].append(name)

    # Now that we have knowledge of duplicates, uniquify the sequences
    duplicates_per_node = []
    sequences = {}
    for key, value in duplicate_counter.items():
        name, duplicates = value
        sequences[name] = key
        duplicates_per_node.append(duplicates)

    return sequences, duplicates_per_node



def average_profile(nodes: list, lambda1: float) -> list:
    """Calculates the average of profiles of internal nodes

    Args:
        nodes: List of two Nodes whose average profile is calculated
        lambda1 (float): lambda value BIONJ
    Returns:
        Average profile (list): the profile matrix containing average of two profiles
    """
    p1 = nodes[0].profile
    p2 = nodes[1].profile

    ptotal = []
    for i in range(len(p1)):
        pbase = []
        for j in range(4):
            pbase.append((p1[i][j] * lambda1 + p2[i][j] * (1 - lambda1)))
        ptotal.append(pbase)

    return ptotal



def create_join(ft: Tree, best_join) -> None:
    """Create a new Node and join the best two nodes under it.
    Join two nodes.

    Args:
        ft (Tree): A Tree object
        best_join (tuple(Node, Node)): The two Nodes to be joined

    Returns:
        None
    """
    # calculate BIONJ weights of join with the number of active nodes before the join takes place
    ft.update_lambda(best_join)
    
    # Save just calculated profile of joining nodes to a Node with name containing both joined nodes and make this new node active
    new_node = Node(str(best_join[0].name) + '&' + str(best_join[1].name), len(ft.nodes), 'nosequence', 1)
    new_node.profile = average_profile([best_join[0], best_join[1]], ft.lambda1)

    # add indices of left child, right child
    new_node.leftchild = best_join[0].index
    new_node.rightchild = best_join[1].index
    ft.nodes[best_join[0].index].parent = new_node.index
    ft.nodes[best_join[1].index].parent = new_node.index

    # make joined nodes inactive
    ft.nodes[int(best_join[0].index)].active = False
    ft.nodes[int(best_join[1].index)].active = False

    # append the newly joined node to list of nodes
    ft.nodes.append(new_node)

    if ft.verbose == 1:
        print(new_node.name, ft.nodes[best_join[0].index].branchlength)
        print("Merged nodes to: " + new_node.name)
        print("left child: " + str(new_node.leftchild))
        print("right child: " + str(new_node.rightchild))

    # Recalculate total profile T
    # When we do a join, we also need to update the total profile (the average over all active nodes). To
    # compute this profile takes O(nLa) time. However, we can subtract the joined nodes and add the new
    # node to the total profile in O(La) time. (FastTree) recomputes the total profile from scratch every 200
    # iterations to avoid roundoff errors from accumulating, where the choice of 200 is arbitrary. This adds
    # another O(N 2La/200) work.)
    ft.update_T()

    # Update Top-Hits heuristic
    new_node.tophits = heuristics.TopHits(ft.m)
    new_node.tophits.tophits_new_node(ft, new_node)

    # No more top-hits means all nodes have been joined!
    if len(new_node.tophits.list) == 0:
        if ft.verbose == 1:
            print("Newly created node ", new_node.index, " has no top-hits. This means this was the last join!")
            print()
        return

    # Update the best-hit according to FastNJ
    heuristics.fastNJ_update(ft, new_node)


def CreateInitialTopology(ft: Tree) -> None:
    """
    Create the initial topology given a list with all input nodes. 

    Args:
        ft (Tree): Tree object
    """

    # Original number of nodes (nr of sequences)
    nr_leafs = len(ft.nodes)
    for i in range(nr_leafs - 1):
        if ft.verbose == 1:

            active_nodes = []
            for node in ft.nodes:
                if node.active:
                    active_nodes.append(node.index)

            print("Active nodes remaining in initial topology creation : ", active_nodes)


        # With top hits, we can use We use the FastNJ and local hill-climbing heuristics,
        # with the further restriction that we consider only the top m candidates at each step

        # First find the best m joins among the best-hit entries for the n active nodes
        # FastTree simply sorts all n entries, but the paper suggests a speed-up using a PriorityQueue!
        best_m_joins = PriorityQueue()
        for node in ft.nodes:
            if not node.active:
                continue

            # Fix FastNJ references to inactive notes the "lazy" way
            if not ft.nodes[node.best_join[1]].active:
                # No more top-hits means the heuristic has served its purpose
                if len(node.tophits.list) == 0:
                    minimized_join = neighbor_joining.minimize_nj_criterion(ft)
                    create_join(ft, minimized_join)
                    break

                heuristics.fastNJ_update(ft, node)

            # Put in the best join pair (node, best_join)
            best_m_joins.put((node.best_join[0], (node.index, node.best_join[1])))

        # Then, we compute the current value of the neighbor-joining criterion for those m candidates,
        # which takes O(mLa) time
        best_candidate = (0, 0)  # (distance, node index)]
        min_dist = sys.maxsize / 2
        for _ in range(ft.m):
            if best_m_joins.empty():
                if best_candidate == (0, 0):  # The candidate did not change, so we have reached the end
                    return
                else:
                    break

            candidate = best_m_joins.get()[1]

            i = ft.nodes[candidate[0]]
            j = ft.nodes[candidate[1]]

            criterion = neighbor_joining.nj_criterion(ft, i, j)

            if criterion < min_dist:  # if best join for now
                best_candidate = candidate
                min_dist = criterion

        # Given this candidate join, we do a local hill-climbing search for a better join
        best_join = heuristics.local_hill_climb(ft, best_candidate, min_dist)

        if ft.verbose == 1:
            print("Best Join after heuristics is nodes ", best_join[0].index, best_join[1].index)
            print()

        # Make the join
        create_join(ft, best_join)


def NNI(ft: Tree):
    if ft.verbose == 1:
        print('start NNI')
    nn = sum([node.leaf for node in ft.nodes])  # number of leaf nodes = number of unique sequences

    if ft.verbose == 1:
        print('#nodes:', len(ft.nodes))
        print('#rounds:', round(math.log(nn) + 1))

    # Repeat log2(N)+1 times
    for ii in range(round(math.log(nn, 2) + 1)):
        # Loop over all nodes

        if ft.verbose == 1:
            print("\n NEW NNI ROUND, lambda = ", ft.lambda1)

        for node in ft.nodes:
            # Find what other nodes it can be fixed with (and nodes that are attached to them so which ones to compare)

            # skip all leaf nodes as you cannot fix them to try a new topology
            if node.leaf:
                continue
            # skip if ii is the root node
            if node.parent is None:
                continue
            # if jj is root node: choose right child of the root as jj, and both its children as cc and dd
            if ft.nodes[node.parent].parent is None:
                if ft.verbose == 1:
                    print("exception: jj is root node")
                if ft.nodes[node.parent].leftchild == node.index:
                    jj = ft.nodes[node.parent].rightchild
                if ft.nodes[node.parent].rightchild == node.index:
                    jj = ft.nodes[node.parent].leftchild
                cc = ft.nodes[jj].rightchild  # child of second fixed node (jj)
                dd = ft.nodes[jj].leftchild  # child of second fixed node (jj)

            else:
                # node ii is fixed together with its parent jj
                jj = node.parent
                dd = ft.nodes[jj].parent  # parent of the second fixed node (jj)
                if ft.nodes[node.parent].leftchild == node.index:
                    cc = ft.nodes[jj].rightchild  # child of second fixed node (jj)
                if ft.nodes[node.parent].rightchild == node.index:
                    cc = ft.nodes[jj].leftchild  # child of second fixed node (jj)

            if ft.verbose == 1:
                print('ii', node.index)
                print('jj', jj)

            # get the indices of the nodes that can be swapped
            aa = node.leftchild  # child of original node
            bb = node.rightchild  # child of original node

            if ft.verbose == 1:
                print('NNI compares', ft.nodes[aa].index, ft.nodes[bb].index, ft.nodes[cc].index, ft.nodes[dd].index)

            # For each possible combination of fixed nodes, find the best topology
            best_top = MinimizedEvolution(ft, ft.nodes[aa], ft.nodes[bb], ft.nodes[cc], ft.nodes[dd])
            if ft.verbose == 1:
                print('NNI best topology', best_top[0][0].index, best_top[0][1].index, best_top[1][0].index,
                  best_top[1][1].index)

            # Do all switches

            # maximum of one switch can be made per round, stop checking if switch was found
            # ss is never switched, no need to check
            # if rr is switched, the switch is already taken care of when checking jj or kk, no need to check again

            if aa != best_top[0][0].index:
                # swap nodes
                index_swap = best_top[0][0].index   # save indices of nodes that should be swapped
                index_aa = aa

                parent_aa = ft.nodes[index_aa].parent  # save parent
                parent_swap = ft.nodes[index_swap].parent

                ft.nodes[index_aa].parent = parent_swap        # change their new parents
                ft.nodes[index_swap].parent = parent_aa

                # change children of the parents
                if ft.nodes[parent_aa].leftchild == index_aa:
                    ft.nodes[parent_aa].leftchild = index_swap
                elif ft.nodes[parent_aa].rightchild == index_aa:
                    ft.nodes[parent_aa].rightchild = index_swap
                else:
                    print("ERROR in children swap in NNI")
                if ft.nodes[parent_swap].leftchild == index_swap:
                    ft.nodes[parent_swap].leftchild = index_aa
                elif ft.nodes[parent_swap].rightchild == index_swap:
                    ft.nodes[parent_swap].rightchild = index_aa
                else:
                    print("ERROR in children swap in NNI")

            elif bb != best_top[0][1].index:

                # swap nodes
                index_swap = best_top[0][1].index       # save indices of nodes that should be swapped
                index_bb = bb

                parent_bb = ft.nodes[index_bb].parent   # save parent index
                parent_swap = ft.nodes[index_swap].parent

                ft.nodes[index_bb].parent = parent_swap            # change their new parents
                ft.nodes[index_swap].parent = parent_bb

                # change children of the parents
                if ft.nodes[parent_bb].leftchild == index_bb:
                    ft.nodes[parent_bb].leftchild = index_swap
                elif ft.nodes[parent_bb].rightchild == index_bb:
                    ft.nodes[parent_bb].rightchild = index_swap
                else:
                    print("ERROR in children swap in NNI")
                if ft.nodes[parent_swap].leftchild == index_swap:
                    ft.nodes[parent_swap].leftchild = index_bb
                elif ft.nodes[parent_swap].rightchild == index_swap:
                    ft.nodes[parent_swap].rightchild = index_bb
                else:
                    print("ERROR in children swap in NNI")

        # Recompute profiles of internal nodes
        for node in ft.nodes:
            if node.leaf:  # skip all leaf nodes
                continue
            node.profile = average_profile([ft.nodes[node.leftchild], ft.nodes[node.rightchild]], ft.lambda1)
    if ft.verbose == 1:
        print('NNI finished')

    return ft.nodes


def MinimizedEvolution(ft: Tree, n1, n2, n3, n4):
    """ Evaluate all possible topologies with four nodes surrounding two fixed nodes
    and find the topology that minimizes the evolution citerion.

    Args:
        n1 (node): node

    Returns:
        best_topology (list): list of lists that contain the nodes that form the best topology

    """

    # All possible topologies involving these nodes
    option1 = [[n1, n2], [n3, n4]]
    option2 = [[n1, n3], [n2, n4]]
    option3 = [[n3, n2], [n1, n4]]
    options = [option1, option2, option3]

    # Calculate the evolution criterion for each possible topology
    dist_options = []
    for ii in range(len(options)):
        dist_a = util.JC_distance(util.uncorrected_distance(ft, [options[ii][0][0], options[ii][0][1]]))
        dist_b = util.JC_distance(util.uncorrected_distance(ft, [options[ii][1][0], options[ii][1][1]]))
        dist_options.append(dist_a + dist_b)

    # Choose the topology with the minimized criterion
    best_topology = options[dist_options.index(min(dist_options))]

    return best_topology

"""

"""

from src.tree import Tree
from src.node import Node


def uncorrected_distance(ft: Tree, join: list):
    """Uncorrected distance between joined nodes (node_ij) and other nodes (node_k)
    du(ij, k) = ∆(ij, k) − u(ij) − u(k)
    args;
        list with input nodes
        indices of nodes which are joined
    returns:
        uncorrected Distance
    """
    if len(join) == 2:
        indices = [join[0].index, join[1].index]
        # du(i, j) = ∆(i, j)−u(i)−u(j), where u(i) = 0 and u(j) = 0 as i and j are leaves
        del_ij = profile_distance_new([ft.nodes[indices[0]].profile, ft.nodes[indices[1]].profile])
        return del_ij
    if len(join) == 3:
        indices = [join[0], join[1], join[2].index]
        del_ijk = profile_distance_nodes(ft, indices)
        u_ij = updistance(ft.nodes, [indices[0], indices[1]])
        u_k = updistance(ft.nodes, [indices[2]])
        du_ijk = del_ijk - u_ij - u_k
        return du_ijk


def profile_distance_new(profiles: list) -> float:
    """Calculates “profile distance” that is the average distance between profile characters over all positions

    input:
        list of profiles of which you want to calculate profile distance (i,j)

    returns:
        profile distance ∆(i, j)
    """
    value = 0
    for L in range(len(profiles[0])):
        for a in range(4):
            for b in range(4):
                if profiles[0][L][a] > 0 and profiles[1][L][a] > 0:
                    P = 0
                else:
                    P = 1
                value += profiles[0][L][a] * profiles[1][L][b] * P

    return value / len(profiles)


def profile_distance_nodes(ft: Tree, indices: list) -> float:
    """∆(ij, k)
        indices [i, j, k]
        ∆(ij, k) = λ∆(i, k) + (1 − λ)∆(j, k)
        profile of parent after joining i and j

        Args:
            ft: Tree object
            indices: index of nodes [i, j, k]
        Returns:
            float: Profile distance between joined nodes and other nodes
        """

    profile_dist = ft.lambda1 * \
                   (profile_distance_new([ft.nodes[indices[0]].profile, ft.nodes[indices[2]].profile])) + \
                   (1 - ft.lambda1) * \
                   (profile_distance_new([ft.nodes[indices[1]].profile, ft.nodes[indices[2]].profile]))
    return profile_dist


def updistance(nodes: list, ijk: list):
    """Calculate updistance with formula's:
            u(ij) ≡ ∆(i, j)/2
            u(k) has kids so look at leftchild and rightchild so becomes u(k_leftchild, k_rightchild)
            u(k) = o for leaves

    Args:
        list with all nodes
        list with nodes for which the updistance should be calculated
             (could have a length of 1 or 2 depending on u(ij) or u(k))
    returns:
        updistance u(ij) or u(k)
    """
    if len(ijk) > 1:
        return profile_distance_new([nodes[ijk[0]].profile, nodes[ijk[1]].profile]) / 2
    elif nodes[ijk[0]].leaf:
        return 0
    else:
        return profile_distance_new(
            [nodes[nodes[ijk[0]].rightchild].profile, nodes[nodes[ijk[0]].leftchild].profile]) / 2


def out_distance_new(ft: Tree, i: Node) -> float:
    """The average profile distance between a node and all other
       nodes can be inferred from the total profile T: r(i) = (n∆(i, T) − ∆(i, i) − (n − 1)u(i) + u(i) − sum u(j))/(n-2)

    Args:
        active nodes; list of nodes; T total profile of current topology
    returns:
        out distance of one node
    """

    N_active_nodes = 1  # i is always an active node; is
    sumJ = 0
    for j in ft.nodes:
        if j.name == i:
            continue
        if not j.active:
            continue
        N_active_nodes += 1
        sumJ += updistance(ft.nodes, [j.index])
    # !!!!!!!!!! ∆(i, i) snap ik niet
    sum_du_ij = N_active_nodes * profile_distance_new([i.profile, ft.T]) - profile_distance_new(
        [i.profile, i.profile]) - (
                        N_active_nodes - 1) * updistance(ft.nodes, [i.index]) + updistance(ft.nodes, [i.index]) - sumJ
    if N_active_nodes == 2:
        return sum_du_ij
    return sum_du_ij / (N_active_nodes - 2)
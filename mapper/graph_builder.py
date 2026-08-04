"""
CodePhoenix — Unified Graph Builder

Aggregates individual CFGs and ASTs into a massive, project-wide Knowledge Graph.
Uses NetworkX for building the graph and mapping dependencies.
"""

from __future__ import annotations
import networkx as nx
from typing import Iterator

from codephoenix.models import (
    GraphNode,
    GraphEdge,
    EdgeType,
    ParsedFile,
)
from codephoenix.mapper.cfg_builder import build_cfg


class KnowledgeGraph:
    """Project-wide dependency and logic graph."""
    
    def __init__(self):
        # We use a directed graph to represent control flow, calls, and data dependencies
        self.graph = nx.DiGraph()
        
    def add_node(self, node: GraphNode):
        """Add a unified graph node."""
        self.graph.add_node(
            node.id,
            node_type=node.node_type,
            label=node.label,
            file_path=node.file_path,
            start_line=node.start_line,
            end_line=node.end_line,
            **node.properties
        )
        
    def add_edge(self, edge: GraphEdge):
        """Add a unified graph edge."""
        self.graph.add_edge(
            edge.source_id,
            edge.target_id,
            edge_type=edge.edge_type.name,
            **edge.properties
        )

    def ingest(self, parsed_file: ParsedFile):
        """
        Ingest a parsed file into the global knowledge graph.
        Builds CFGs for procedures and adds them.
        """
        file_node_id = f"FILE:{parsed_file.source_file.path.name}"
        
        # Add file node
        self.add_node(GraphNode(
            id=file_node_id,
            node_type="file",
            label=parsed_file.source_file.path.name,
            file_path=str(parsed_file.source_file.path),
            properties={"language": parsed_file.source_file.language.name}
        ))
        
        # Process Variables
        for var in parsed_file.variables:
            var_id = f"VAR:{parsed_file.source_file.path.name}:{var.name}"
            self.add_node(GraphNode(
                id=var_id,
                node_type="variable",
                label=var.name,
                file_path=str(parsed_file.source_file.path),
                start_line=var.start_line,
                properties=var.properties
            ))
            # Edge: File CONTAINS Variable
            self.add_edge(GraphEdge(
                source_id=file_node_id,
                target_id=var_id,
                edge_type=EdgeType.CONTAINS
            ))
            
        # Process Procedures & CFGs
        cfgs = build_cfg(parsed_file)
        
        for cfg in cfgs:
            proc_id = f"PROC:{parsed_file.source_file.path.name}:{cfg.procedure_name}"
            
            # Add Procedure Node
            self.add_node(GraphNode(
                id=proc_id,
                node_type="procedure",
                label=cfg.procedure_name,
                file_path=str(parsed_file.source_file.path),
                properties={"complexity": cfg.cyclomatic_complexity}
            ))
            
            # Edge: File CONTAINS Procedure
            self.add_edge(GraphEdge(
                source_id=file_node_id,
                target_id=proc_id,
                edge_type=EdgeType.CONTAINS
            ))
            
            # Add Basic Blocks & CFG Edges
            cfg_nodes, cfg_edges = cfg.to_graph_nodes_edges()
            for node in cfg_nodes:
                self.add_node(node)
                # Edge: Procedure CONTAINS Basic Block
                self.add_edge(GraphEdge(
                    source_id=proc_id,
                    target_id=node.id,
                    edge_type=EdgeType.CONTAINS
                ))
                
            for edge in cfg_edges:
                self.add_edge(edge)
                
        # Resolve Calls (Intra-file for now; inter-file requires a second pass)
        for call in parsed_file.calls:
            # We assume the call name matches a procedure name in the file for this pass.
            target_proc_id = f"PROC:{parsed_file.source_file.path.name}:{call.name}"
            
            # Find the basic block that contains this call
            src_bb_id = None
            for cfg in cfgs:
                for block in cfg.blocks:
                    if block.start_line <= call.start_line <= block.end_line:
                        src_bb_id = block.id
                        break
                if src_bb_id:
                    break
            
            if src_bb_id:
                self.add_edge(GraphEdge(
                    source_id=src_bb_id,
                    target_id=target_proc_id,
                    edge_type=EdgeType.CALLS
                ))

    def get_subgraph(self, node_id: str, radius: int = 2) -> nx.DiGraph:
        """Extract a subgraph around a specific node for LLM context."""
        if node_id not in self.graph:
            return nx.DiGraph()
        
        # Get nodes within 'radius' hops
        nodes_to_include = {node_id}
        current_layer = {node_id}
        
        for _ in range(radius):
            next_layer = set()
            for n in current_layer:
                next_layer.update(self.graph.successors(n))
                next_layer.update(self.graph.predecessors(n))
            nodes_to_include.update(next_layer)
            current_layer = next_layer
            
        return self.graph.subgraph(nodes_to_include)

    def export_graphml(self, filepath: str):
        """Export the graph to GraphML format for visualization."""
        nx.write_graphml(self.graph, filepath)

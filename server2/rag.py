"""
In-memory RAG system using LangChain and Gemini.

This module provides retrieval-augmented generation capabilities
for the emergency dispatch agent using LangChain and Google Gemini.
"""

import logging
from typing import List, Optional

# LangChain imports (optional - RAG requires these packages)
try:
    from langchain_core.documents import Document
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    Document = None  # type: ignore
    RecursiveCharacterTextSplitter = None  # type: ignore

# Try different import paths for InMemoryVectorStore
InMemoryVectorStore = None  # type: ignore
try:
    from langchain_core.vectorstores import InMemoryVectorStore
except ImportError:
    try:
        from langchain_community.vectorstores import InMemoryVectorStore
    except ImportError:
        try:
            from langchain.vectorstores import InMemoryVectorStore
        except ImportError:
            pass  # Will use simple fallback

# LangChain Google integration for embeddings
try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
except ImportError:
    GoogleGenerativeAIEmbeddings = None  # type: ignore

from server2.config import get_settings
from server2.logging_utils import ErrorComponent, get_logger

logger = get_logger("anya.server2.rag")

# Emergency dispatch knowledge base
EMERGENCY_KNOWLEDGE_BASE = """
# 112 Emergency Response Support System - Knowledge Base

## Fire Emergencies
- For building fires: Evacuate immediately, do not use elevators
- For electrical fires: Do not use water, use CO2 extinguisher
- For gas fires: Shut off gas supply if safe, evacuate area
- Alert Fire Department at 101 or 112

## Medical Emergencies
- Cardiac arrest: Start CPR immediately, call ambulance
- Bleeding: Apply direct pressure, elevate injured area
- Choking: Perform Heimlich maneuver if conscious
- Burns: Cool with running water for 20 minutes, cover with sterile dressing
- Fractures: Immobilize the injured area, do not attempt to realign
- Alert Ambulance at 102 or 112

## Police / Crime Emergencies
- Active shooter: Run, Hide, Fight protocol
- Theft: Secure area, note descriptions, do not confront
- Assault: Ensure victim safety, call police immediately
- Vandalism: Document damage, file report
- Alert Police at 100 or 112

## Natural Disasters
- Earthquake: Drop, Cover, Hold On. Evacuate after shaking stops
- Flood: Move to higher ground, do not walk through moving water
- Cyclone: Stay indoors, away from windows, secure loose objects
- Landslide: Evacuate perpendicular to landslide direction

## Traffic Accidents
- Minor accidents: Move to roadside, exchange information
- Major accidents: Do not move victims unless in danger
- Hit and run: Note vehicle details, report to police
- Highway emergency: Call highway patrol at 103

## Infrastructure Failures
- Power outage: Check circuit breaker, report to utility
- Water main break: Locate shut-off valve, call water department
- Gas leak: Evacuate area, do not use electrical switches
- Bridge collapse: Stay clear, alert authorities

## Chemical / Hazmat Incidents
- Chemical spill: Evacuate upwind, do not touch material
- Fumes/Gas leak: Evacuate area, alert fire department
- Radiation exposure: Decontaminate if trained, seek medical help
- Biological hazard: Isolate area, contact hazmat team

## Priority Codes
- Code Red: Life-threatening, immediate response required
- Code Orange: Serious but not immediately life-threatening
- Code Yellow: Moderate urgency, monitor situation
- Code Green: Non-emergency, routine response

## Department Coordination
- Fire Department: Fire suppression, rescue, hazmat
- Police: Law enforcement, crowd control, security
- Ambulance/Medical: Triage, treatment, transport
- Disaster Response: Large-scale incident management
- Electrical: Power restoration, electrical hazards
- Public Works: Road clearing, debris removal
- Utilities: Gas, water, sewage restoration

## Location Information
- Provide landmark references when possible
- Note nearby intersections or major roads
- Describe building type and color
- Mention floor number for high-rise buildings
- Provide GPS coordinates if available

## Caller Information to Collect
- Name and contact number
- Exact location of emergency
- Type of emergency
- Number of people involved
- Any hazards present
- Current status of situation

## Communication Best Practices
- Speak clearly and calmly
- Follow dispatcher instructions precisely
- Do not hang up until told to do so
- Provide accurate information, avoid speculation
- Stay on line for updates
"""


class InMemoryRAG:
    """
    In-memory RAG system using LangChain and Gemini embeddings.

    This system stores emergency knowledge in memory and retrieves
    relevant context based on user queries.
    """

    def __init__(self):
        self._vector_store = None
        self._embeddings = None
        self._initialized = False
        self._documents = []  # Fallback: store documents directly

    def initialize(self):
        """Initialize the RAG system with knowledge base."""
        print("\n[RAG] → Initializing RAG system...")

        if not LANGCHAIN_AVAILABLE:
            logger.warning("LangChain not available, RAG disabled")
            print("[RAG] ✗ LangChain not available, RAG disabled")
            return

        settings = get_settings()

        if not settings.GEMINI_API_KEY:
            logger.warning("GEMINI_API_KEY not set, RAG disabled")
            print("[RAG] ✗ GEMINI_API_KEY not set, RAG disabled")
            return

        try:
            print(f"[RAG]   → Creating embeddings with model: models/gemini-embedding-001")
            # Initialize embeddings with Gemini
            # Use correct model name for Google GenAI API
            self._embeddings = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=settings.GEMINI_API_KEY,
            )

            # Create text splitter
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.RAG_CHUNK_SIZE,
                chunk_overlap=settings.RAG_CHUNK_OVERLAP,
            )

            # Split knowledge base into chunks
            chunks = text_splitter.split_text(EMERGENCY_KNOWLEDGE_BASE)

            # Create documents
            documents = [
                Document(page_content=chunk, metadata={"source": "emergency_kb"})
                for chunk in chunks
            ]

            # Create in-memory vector store
            print(f"[RAG]   → Splitting knowledge base into {len(chunks)} chunks...")
            if InMemoryVectorStore is not None:
                print(f"[RAG]   → Creating vector store with embeddings...")
                self._vector_store = InMemoryVectorStore.from_documents(
                    documents=documents,
                    embedding=self._embeddings,
                )
                print(f"[RAG]   ✓ Vector store created")
            else:
                # Fallback: store documents directly and use simple matching
                self._documents = documents
                print(f"[RAG]   ⚠ Using simple document storage (vector store not available)")
                logger.info("InMemoryVectorStore not available, using simple document storage")

            self._initialized = True
            print(f"[RAG] ✓ RAG initialized with {len(documents)} chunks\n")
            logger.info(f"RAG initialized with {len(documents)} chunks")

        except Exception as e:
            logger.error(
                f"Failed to initialize RAG: {str(e)}",
                component=ErrorComponent.RAG,
                include_traceback=True,
            )
            self._initialized = False

    async def retrieve_context(self, query: str, top_k: Optional[int] = None) -> str:
        """
        Retrieve relevant context for a query.

        Args:
            query: The user's query
            top_k: Number of chunks to retrieve (default from settings)

        Returns:
            Retrieved context as a string
        """
        print(f"[RAG] → Retrieving context for query: {query[:50]}...")

        if not self._initialized:
            # Initialize if not already done
            print(f"[RAG]   Not initialized, initializing...")
            self.initialize()

        if not self._initialized:
            print(f"[RAG] ✗ Failed to initialize")
            return ""

        try:
            settings = get_settings()
            k = top_k or settings.RAG_TOP_K

            # Use vector store if available
            if self._vector_store is not None:
                print(f"[RAG]   → Searching vector store (top_k={k})...")
                results = self._vector_store.similarity_search(
                    query=query,
                    k=k,
                )
                context_chunks = [doc.page_content for doc in results]
                print(f"[RAG]   ✓ Found {len(results)} relevant chunks")
            else:
                # Fallback: simple keyword matching
                print(f"[RAG]   → Using keyword matching (vector store not available)...")
                query_lower = query.lower()
                scored_docs = []
                for doc in self._documents:
                    score = sum(1 for word in query_lower.split() if word in doc.page_content.lower())
                    if score > 0:
                        scored_docs.append((score, doc))
                scored_docs.sort(reverse=True, key=lambda x: x[0])
                context_chunks = [doc.page_content for _, doc in scored_docs[:k]]
                print(f"[RAG]   ✓ Found {len(context_chunks)} relevant chunks")

            context = "\n\n---\n\n".join(context_chunks)
            print(f"[RAG] ✓ Context retrieved ({len(context)} chars)\n")

            logger.debug(f"Retrieved {len(context_chunks)} chunks for query: {query[:50]}...")
            return context

        except Exception as e:
            logger.error(
                f"Error retrieving context: {str(e)}",
                component=ErrorComponent.RAG,
                query=query[:100],  # First 100 chars
            )
            return ""

    def is_available(self) -> bool:
        """Check if RAG is available."""
        return self._initialized

    def add_documents(self, texts: List[str], metadata: Optional[dict] = None):
        """
        Add additional documents to the knowledge base.

        Args:
            texts: List of text documents to add
            metadata: Optional metadata to attach to documents
        """
        if not self._initialized or not self._vector_store:
            logger.warning("RAG not initialized, cannot add documents")
            return

        try:
            documents = [
                Document(page_content=text, metadata=metadata or {})
                for text in texts
            ]

            self._vector_store.add_documents(documents)
            logger.info(f"Added {len(documents)} documents to RAG")

        except Exception as e:
            logger.error(
                f"Error adding documents: {str(e)}",
                component=ErrorComponent.RAG,
                document_count=len(texts),
            )


# Global RAG instance
rag_system = InMemoryRAG()
